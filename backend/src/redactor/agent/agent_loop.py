"""Agent loop for managing tool execution and conversation flow."""

from typing import Any, Dict, List, Optional
import logging
import uuid

from openai import AsyncAzureOpenAI

from redactor.agent.tools.registry import ToolRegistry
from redactor.agent.knowledge_base import KnowledgeBase
from redactor.config import get_settings

logger = logging.getLogger(__name__)


class AgentLoop:
    """Main agent loop for managing tool calling and conversation flow."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        oai_client: AsyncAzureOpenAI,
        knowledge_base: Optional[KnowledgeBase] = None,
        max_tool_rounds: int = 10,
    ):
        """Initialize agent loop.

        Args:
            tool_registry: Registry of available tools
            oai_client: Azure OpenAI client
            knowledge_base: Optional knowledge base for context
            max_tool_rounds: Maximum number of tool execution rounds
        """
        self.tool_registry = tool_registry
        self.oai_client = oai_client
        self.knowledge_base = knowledge_base
        self.max_tool_rounds = max_tool_rounds
        self.settings = get_settings()

    async def run_turn(
        self,
        user_message: str,
        job_id: str,
        workspace_id: Optional[str] = None,
        session_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run a single agent turn with tool execution.

        Args:
            user_message: User's message
            job_id: Current job ID for context
            workspace_id: Optional workspace ID for context
            session_messages: Previous session messages for context

        Returns:
            Dict with text response, tool calls, and directives
        """
        try:
            # Prepare messages for API call
            messages = self._build_messages(user_message, session_messages, job_id, workspace_id)
            tool_calls_list: List[Dict[str, Any]] = []
            directives: List[Dict[str, Any]] = []

            # Get available tools as OpenAI functions
            tools = self.tool_registry.get_openai_functions()

            # Initial API call
            response = await self.oai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                temperature=0.2,
                max_tokens=1000,
            )

            # Process response and execute tools in loop
            final_text = ""
            rounds = 0

            while rounds < self.max_tool_rounds:
                # Check for tool calls
                if response.choices[0].message.tool_calls:
                    tool_calls = response.choices[0].message.tool_calls
                    assistant_message = response.choices[0].message

                    # Add assistant message to conversation
                    messages.append({"role": "assistant", "content": assistant_message.content or ""})

                    # Execute each tool call
                    tool_results = []
                    for tool_call in tool_calls:
                        tool_result = await self._execute_tool(tool_call)
                        tool_calls_list.append({
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                            "result": tool_result.to_dict() if hasattr(tool_result, 'to_dict') else tool_result
                        })
                        tool_results.append({
                            "tool_use_id": tool_call.id,
                            "content": str(tool_result.data if hasattr(tool_result, 'data') else tool_result)
                        })

                    # Add tool results to messages
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": result["tool_use_id"],
                                "content": result["content"]
                            }
                            for result in tool_results
                        ]
                    })

                    # Continue conversation
                    response = await self.oai_client.chat.completions.create(
                        model=self.settings.azure_openai_deployment,
                        messages=messages,
                        tools=tools if tools else None,
                        tool_choice="auto" if tools else None,
                        temperature=0.2,
                        max_tokens=1000,
                    )

                    rounds += 1
                else:
                    # No more tool calls, get final text response
                    final_text = response.choices[0].message.content or ""
                    break

            return {
                "text": final_text,
                "response_id": str(uuid.uuid4()),
                "tool_calls": tool_calls_list,
                "directives": directives,
            }

        except Exception as e:
            logger.exception("Error in agent loop")
            return {
                "text": f"Error processing request: {str(e)}",
                "response_id": None,
                "tool_calls": [],
                "directives": [],
            }

    async def _execute_tool(self, tool_call: Any) -> Any:
        """Execute a single tool call.

        Args:
            tool_call: Tool call from OpenAI response

        Returns:
            Tool result
        """
        tool_name = tool_call.function.name
        tool = self.tool_registry.get(tool_name)

        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        try:
            # Parse arguments
            import json
            arguments = json.loads(tool_call.function.arguments)

            # Execute tool
            result = await tool.execute(**arguments)
            return result
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            return {"success": False, "error": str(e)}

    def _build_messages(
        self,
        user_message: str,
        session_messages: Optional[List[Dict[str, Any]]],
        job_id: str,
        workspace_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Build message list for API call.

        Args:
            user_message: Current user message
            session_messages: Previous messages
            job_id: Job ID for context
            workspace_id: Workspace ID for context

        Returns:
            List of messages for API
        """
        messages: List[Dict[str, Any]] = []

        # System message
        system_content = self._build_system_prompt(job_id, workspace_id)
        messages.append({"role": "system", "content": system_content})

        # Add previous session messages
        if session_messages:
            for msg in session_messages[-6:]:  # Last 6 messages for context
                if msg.get("role") in {"user", "assistant"} and msg.get("content"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

        # Add current message
        messages.append({"role": "user", "content": user_message})

        return messages

    def _build_system_prompt(self, job_id: str, workspace_id: Optional[str]) -> str:
        """Build system prompt with context.

        Args:
            job_id: Current job ID
            workspace_id: Current workspace ID

        Returns:
            System prompt string
        """
        prompt = (
            "You are an intelligent PDF redaction assistant with access to tools for searching documents, "
            "managing workspace rules, and organizing redaction workflows. "
            "Help users search documents, manage workspace state, create and apply redaction rules, "
            "and exclude documents from automation. "
            "Be explicit about scope when multiple documents are involved. "
            "Always respect workspace exclusions."
        )

        if workspace_id:
            prompt += f"\nCurrent workspace context: {workspace_id}"

        if job_id:
            prompt += f"\nActive document: {job_id}"

        return prompt
