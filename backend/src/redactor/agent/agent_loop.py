from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging
from redactor.agent.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from redactor.agent.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


class AgentLoop:
    """Main agent execution loop with tool handling."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        oai_client,
        knowledge_base: Optional["KnowledgeBase"] = None,
        max_tool_rounds: int = 10
    ):
        self.tool_registry = tool_registry
        self.oai_client = oai_client
        self.knowledge_base = knowledge_base
        self.max_tool_rounds = max_tool_rounds

    async def execute_tool(self, tool_use: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool and return result.

        Args:
            tool_use: Dict with "name" and "arguments" keys

        Returns:
            Dict with "success", "data", and optional "error" keys
        """
        tool_name = tool_use.get("name")
        arguments = tool_use.get("arguments", {})

        tool = self.tool_registry.get(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found in registry"
            }

        try:
            result = await tool.execute(**arguments)
            return {
                "success": result.success,
                "data": result.data,
                "error": result.error
            }
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }

    async def run_turn(
        self,
        user_message: str,
        job_id: str,
        workspace_id: Optional[str] = None,
        session_messages: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Run one agent turn: send message to LLM, execute tools, return response.

        Returns:
            Dict with "text", "tool_calls", and "directives"
        """
        if not self.oai_client:
            return {
                "text": "Agent not configured",
                "tool_calls": [],
                "directives": []
            }

        tool_calls = []
        session_messages = session_messages or []

        # Build system prompt
        system_prompt = self._build_system_prompt(job_id, workspace_id)

        # Build messages for LLM
        messages = [
            {"role": "system", "content": system_prompt},
            *session_messages,
            {"role": "user", "content": user_message}
        ]

        # Get response from LLM with tools
        try:
            response = await self.oai_client.chat.completions.create(
                model="gpt-4",  # Will use config value in real implementation
                messages=messages,
                tools=self.tool_registry.get_openai_functions(),
                temperature=0.2,
                max_tokens=500
            )

            # Process response and execute tools
            assistant_message = response.choices[0].message.content or ""

            # Check for tool calls
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    tool_result = await self.execute_tool({
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    })
                    tool_calls.append(tool_result)

            return {
                "text": assistant_message,
                "tool_calls": tool_calls,
                "directives": []
            }

        except Exception as e:
            logger.exception("Error in agent loop")
            return {
                "text": f"Error: {str(e)}",
                "tool_calls": [],
                "directives": []
            }

    def _build_system_prompt(self, job_id: str, workspace_id: Optional[str] = None) -> str:
        """Build system prompt for the agent."""
        prompt = (
            "You are a PDF redaction assistant. "
            "Help users manage document redaction using available tools. "
            f"Current document: {job_id}. "
        )

        if workspace_id:
            prompt += f"Current workspace: {workspace_id}. "

        prompt += (
            "Use tools to search documents, manage rules, and control exclusions. "
            "Be explicit about scope and limitations."
        )

        return prompt
