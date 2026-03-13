"""Workspace-aware agent orchestration with tool execution and directives."""

from typing import Any, Optional
import logging
import uuid

from openai import AsyncAzureOpenAI

from redactor.agent.tools.registry import ToolRegistry
from redactor.agent.knowledge_base import KnowledgeBase
from redactor.config import get_settings

logger = logging.getLogger(__name__)


class RedactionOrchestrator:
    """Orchestrator for workspace-aware redaction using agent loop with tools."""

    def __init__(
        self,
        oai_client: AsyncAzureOpenAI,
        tool_registry: ToolRegistry,
        knowledge_base: Optional[KnowledgeBase] = None,
    ):
        """Initialize orchestrator with client, tools, and knowledge base.

        Args:
            oai_client: Azure OpenAI async client
            tool_registry: Registry of available tools
            knowledge_base: Optional knowledge base for workspace context
        """
        self.oai_client = oai_client
        self.tool_registry = tool_registry
        self.knowledge_base = knowledge_base
        self.settings = get_settings()
        self.system_prompt = self._create_system_prompt()
        self.max_tool_rounds = 10

    def _create_system_prompt(self) -> str:
        return (
            "You are an intelligent PDF redaction assistant with access to workspace tools. "
            "Help users search documents, manage redaction rules, and perform workspace operations. "
            "Always respect workspace exclusions and be explicit about scope when multiple documents are involved. "
            "Use tools to accomplish tasks and explain your actions to the user."
        )

    async def run_turn(
        self,
        user_message: str,
        job_id: str,
        workspace_context: Optional[dict[str, Any]] = None,
        session_messages: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Run one agent turn with workspace context.

        Sends message to LLM with available tools, executes tool calls,
        and returns response with directives.

        Args:
            user_message: User's input message
            job_id: Current job identifier
            workspace_context: Workspace state dict (if in workspace mode)
            session_messages: Prior conversation messages for context

        Returns:
            Dict with text, response_id, tool_calls, and directives
        """
        if not self.oai_client:
            return {
                "text": "Agent not configured",
                "tool_calls": [],
                "directives": [],
            }

        try:
            # Build context for LLM
            system_context = self._build_system_context(job_id, workspace_context)
            session_messages = session_messages or []

            # Get available tools from registry
            tools = self.tool_registry.get_openai_functions()

            # Call LLM with tools
            response = await self.oai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "system", "content": system_context},
                    *session_messages[-6:],
                    {"role": "user", "content": user_message},
                ],
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=500,
            )

            # Process response
            assistant_message = response.choices[0].message
            text = assistant_message.content or ""
            tool_calls = []
            directives = []

            # Execute tool calls if present
            if hasattr(assistant_message, "tool_calls") and assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    tool_result = await self._execute_tool_call(tool_call)
                    if tool_result:
                        tool_calls.append(tool_result)
                        # Infer directives from tool execution
                        directives.extend(
                            self._infer_directives_from_tool(tool_result, workspace_context)
                        )

            return {
                "text": text,
                "response_id": str(uuid.uuid4()),
                "tool_calls": tool_calls,
                "directives": directives,
            }

        except Exception:
            logger.exception("Error in orchestrator turn")
            return {
                "text": f"Error processing request: {str(e)}",
                "response_id": str(uuid.uuid4()),
                "tool_calls": [],
                "directives": [],
            }

    async def _execute_tool_call(self, tool_call: Any) -> Optional[dict[str, Any]]:
        """Execute a single tool call.

        Args:
            tool_call: Tool call from LLM response

        Returns:
            Dict with tool call info and result, or None on error
        """
        try:
            tool_name = tool_call.function.name
            import json
            args = json.loads(tool_call.function.arguments or "{}")

            tool = self.tool_registry.get(tool_name)
            if not tool:
                logger.warning(f"Tool '{tool_name}' not found in registry")
                return None

            result = await tool.execute(**args)
            return {
                "name": tool_name,
                "arguments": args,
                "result": {
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                },
            }
        except Exception:
            logger.exception("Error executing tool call")
            return None

    def _infer_directives_from_tool(
        self, tool_call: dict[str, Any], workspace_context: Optional[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Infer UI directives based on tool execution results.

        Args:
            tool_call: Executed tool call with results
            workspace_context: Current workspace context

        Returns:
            List of directive dicts for frontend
        """
        directives = []
        tool_name = tool_call.get("name", "")
        result = tool_call.get("result", {})

        # Search tools should jump to first result
        if tool_name == "search_document" and result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict) and data.get("results"):
                first = data["results"][0]
                directives.append({
                    "type": "jump_to_page",
                    "page": first.get("page", 1),
                    "document_id": first.get("document_id"),
                })
                directives.append({
                    "type": "highlight_text",
                    "document_id": first.get("document_id"),
                    "page": first.get("page", 1),
                    "rects": first.get("coords", []),
                })

        # Workspace modifications should refresh workspace
        if tool_name in ("create_workspace_rule", "apply_workspace_rule", "exclude_document"):
            if workspace_context and result.get("success"):
                directives.append({
                    "type": "refresh_workspace",
                    "workspace_id": workspace_context.get("id"),
                })

        return directives

    def _build_system_context(
        self, job_id: str, workspace_context: Optional[dict[str, Any]]
    ) -> str:
        """Build system context string for LLM.

        Args:
            job_id: Current job identifier
            workspace_context: Workspace state if in workspace mode

        Returns:
            Context string for system prompt
        """
        lines = [f"Active document ID: {job_id}"]

        if workspace_context:
            lines.append(f"Active workspace: {workspace_context.get('name', 'Unknown')}")

            docs = workspace_context.get("documents", [])
            lines.append(f"Documents in workspace: {len(docs)}")

            rules = workspace_context.get("rules", [])
            if rules:
                lines.append(f"Active rules: {len(rules)}")

            exclusions = workspace_context.get("exclusions", [])
            if exclusions:
                lines.append(f"Excluded documents: {len(exclusions)}")

        return "\n".join(lines)
