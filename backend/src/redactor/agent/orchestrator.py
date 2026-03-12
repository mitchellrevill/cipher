from __future__ import annotations

"""Workspace-aware redaction orchestrator scaffold."""

from typing import Any
import logging
import uuid

from openai import AsyncAzureOpenAI

from redactor.config import get_settings

logger = logging.getLogger(__name__)


class RedactionOrchestrator:
    """Main orchestrator agent for conversational PDF redaction assistance."""

    def __init__(self, oai_client: AsyncAzureOpenAI):
        self.oai_client = oai_client
        self.settings = get_settings()
        self.tools = self._define_tools()
        self.system_prompt = self._create_system_prompt()
        self.max_tool_rounds = 10

    def _define_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "search_document",
                "description": "Search for text in the current document or workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for"},
                        "doc_id": {"type": "string", "description": "Optional document identifier"},
                    },
                    "required": ["query"],
                },
            },
            {
                "type": "function",
                "name": "get_workspace_state",
                "description": "Return the current workspace documents, rules, and exclusions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string", "description": "Workspace identifier"}
                    },
                    "required": ["workspace_id"],
                },
            },
        ]

    def _create_system_prompt(self) -> str:
        return (
            "You are an intelligent PDF redaction assistant powered by a workspace-aware orchestration layer. "
            "Help users search documents, reason about redaction rules, and explain what actions you take. "
            "Always respect workspace exclusions and be explicit about scope when multiple documents are involved."
        )

    async def run_turn(
        self,
        user_message: str,
        workspace_context: dict[str, Any] | None = None,
        session_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        context_str = self._build_context_string(workspace_context)
        response_text = "I’m ready to help with workspace-aware redaction tasks."
        if context_str:
            response_text += f" Current scope:\n{context_str}"
        if session_messages:
            response_text += f"\nConversation turns loaded: {len(session_messages)}"

        return {
            "text": response_text,
            "response_id": str(uuid.uuid4()),
            "tool_calls": [],
            "directives": [],
        }

    def _build_context_string(self, workspace_context: dict[str, Any] | None) -> str:
        if not workspace_context:
            return ""

        lines: list[str] = []
        lines.append(f"Workspace: {workspace_context.get('name', 'N/A')}")

        documents = workspace_context.get("documents", [])
        exclusions = workspace_context.get("exclusions", [])
        lines.append(f"Documents in workspace: {len(documents)}")
        lines.append(f"Excluded documents: {len(exclusions)}")

        rules = workspace_context.get("rules", [])
        if rules:
            lines.append(f"Active rules: {len(rules)}")

        return "\n".join(lines)
