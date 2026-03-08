import asyncio
import json
import logging
from openai import AsyncAzureOpenAI
from redactor.agent.tools import make_tools
from redactor.config import get_settings

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10

_oai_client: AsyncAzureOpenAI | None = None
_oai_client_lock = asyncio.Lock()


async def _get_client() -> AsyncAzureOpenAI:
    global _oai_client
    if _oai_client is None:
        async with _oai_client_lock:
            if _oai_client is None:  # double-check after acquiring
                settings = get_settings()
                _oai_client = AsyncAzureOpenAI(
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_key,
                    api_version=settings.azure_openai_api_version,
                )
    return _oai_client

SYSTEM_PROMPT = """You are a document redaction assistant. You help users review and refine \
AI-suggested redactions. You have access to tools to search the document, add redactions, \
remove redactions, add exceptions, and get a summary of what has been redacted. \
Always confirm what you have done after using a tool. Be concise and helpful."""

_TOOL_DEFS = [
    {
        "type": "function",
        "name": "get_redaction_summary",
        "description": "Return the current redaction state: counts by category, total approved, total pending.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "type": "function",
        "name": "add_redaction",
        "description": "Add a new redaction rule to the document.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Exact text to redact across all pages"},
                "reason": {"type": "string", "description": "Why this should be redacted"}
            },
            "required": ["text", "reason"]
        }
    },
    {
        "type": "function",
        "name": "remove_redaction",
        "description": "Remove a specific redaction suggestion by its ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "redaction_id": {"type": "string", "description": "The ID of the suggestion to remove"}
            },
            "required": ["redaction_id"]
        }
    },
    {
        "type": "function",
        "name": "add_exception",
        "description": "Prevent a term from being redacted even if detected as PII.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to exclude from redaction"}
            },
            "required": ["text"]
        }
    },
    {
        "type": "function",
        "name": "search_document",
        "description": "Find all redaction suggestions matching the search query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text or phrase to search for"}
            },
            "required": ["query"]
        }
    }
]


async def run_agent_turn(
    job_id: str,
    user_message: str,
    previous_response_id: str | None = None,
) -> dict:
    """Run one turn of the redaction agent using the OpenAI Responses API."""
    settings = get_settings()
    tool_fns = make_tools(job_id)

    client = await _get_client()

    params: dict = dict(
        model=settings.azure_openai_deployment,
        instructions=SYSTEM_PROMPT,
        input=user_message,
        tools=_TOOL_DEFS,
    )
    if previous_response_id:
        params["previous_response_id"] = previous_response_id

    tool_calls_made = []
    rounds = 0

    # Agentic loop: keep running until no more tool calls or max rounds reached
    while rounds < MAX_TOOL_ROUNDS:
        rounds += 1
        response = await client.responses.create(**params)

        # Collect any tool calls in this turn
        calls_this_turn = [
            item for item in (response.output or [])
            if getattr(item, "type", None) == "function_call"
        ]

        if not calls_this_turn:
            break

        # Execute each tool call and feed results back
        tool_results = []
        for call in calls_this_turn:
            fn = tool_fns.get(call.name)
            if fn is None:
                result = f"Unknown tool: {call.name}"
            else:
                try:
                    args = json.loads(call.arguments or "{}")
                    result = fn(**args)
                except Exception as ex:
                    result = f"Tool error: {ex}"
                    logger.exception("Tool %s failed", call.name)

            tool_calls_made.append({"name": call.name, "result": result})
            tool_results.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result) if not isinstance(result, str) else result,
            })

        # Continue the conversation with tool results
        params = dict(
            model=settings.azure_openai_deployment,
            instructions=SYSTEM_PROMPT,
            input=tool_results,
            tools=_TOOL_DEFS,
            previous_response_id=response.id,
        )

    return {
        "text": response.output_text,
        "response_id": response.id,
        "tool_calls": tool_calls_made,
    }
