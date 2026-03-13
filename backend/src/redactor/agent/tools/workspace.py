import json
import logging
from typing import Annotated
from agent_framework import tool
from pydantic import Field

logger = logging.getLogger(__name__)


class WorkspaceTools:
    """Tools for managing workspace state, rules, and document exclusions."""

    def __init__(self, workspace_service):
        self.workspace_service = workspace_service

    @tool(approval_mode="never_require")
    async def get_workspace_state(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
    ) -> str:
        """Return the current workspace documents, rules, and exclusions."""
        if not self.workspace_service:
            return "Error: workspace service not configured"
        try:
            state = await self.workspace_service.get_workspace_state(workspace_id)
            if not state:
                return f"Error: workspace '{workspace_id}' not found"
            return json.dumps({
                "workspace": state,
                "document_count": len(state.get("documents", [])),
                "rule_count": len(state.get("rules", [])),
                "exclusion_count": len(state.get("exclusions", [])),
            })
        except Exception as e:
            logger.exception("Error in get_workspace_state")
            return f"Error: {e}"

    @tool(approval_mode="never_require")
    async def create_rule(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        category: Annotated[str, Field(description="Redaction category (e.g. 'PII', 'CreditCard')")],
        pattern: Annotated[str, Field(description="Pattern or description of what to redact")],
    ) -> str:
        """Create a new redaction rule for a category in the workspace."""
        if not self.workspace_service:
            return "Error: workspace service not configured"
        try:
            result = await self.workspace_service.create_workspace_rule(
                workspace_id,
                {"category": category, "pattern": pattern},
            )
            return json.dumps(result)
        except Exception as e:
            logger.exception("Error in create_rule")
            return f"Error: {e}"

    @tool(approval_mode="never_require")
    async def apply_rule(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        rule_id: Annotated[str, Field(description="Workspace rule identifier to apply")],
    ) -> str:
        """Apply a saved workspace rule across all non-excluded documents."""
        if not self.workspace_service:
            return "Error: workspace service not configured"
        try:
            result = await self.workspace_service.apply_batch_rule(workspace_id, rule_id)
            return json.dumps(result)
        except Exception as e:
            logger.exception("Error in apply_rule")
            return f"Error: {e}"

    @tool(approval_mode="never_require")
    async def exclude_document(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        document_id: Annotated[str, Field(description="Document to exclude from workspace automation")],
        reason: Annotated[str, Field(description="Reason for exclusion")] = "Excluded from automation",
    ) -> str:
        """Exclude a document from workspace rules and automation."""
        if not self.workspace_service:
            return "Error: workspace service not configured"
        try:
            result = await self.workspace_service.exclude_document(workspace_id, document_id, reason)
            return json.dumps(result)
        except Exception as e:
            logger.exception("Error in exclude_document")
            return f"Error: {e}"
