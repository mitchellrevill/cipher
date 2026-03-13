from typing import Any, Dict, Optional
from redactor.agent.tools.base import Tool, ToolResult


class GetWorkspaceStateTool(Tool):
    """Get current workspace state (documents, rules, exclusions)."""

    name = "get_workspace_state"
    description = "Return the current workspace documents, rules, and exclusions."

    def __init__(self, workspace_service=None):
        self.workspace_service = workspace_service

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier"
                }
            },
            "required": ["workspace_id"]
        }

    async def execute(self, workspace_id: str, **kwargs) -> ToolResult:
        """Get workspace state."""
        if not self.workspace_service:
            return ToolResult(success=False, error="Workspace service not configured")

        try:
            state = await self.workspace_service.get_workspace_state(workspace_id)

            if not state:
                return ToolResult(
                    success=False,
                    error=f"Workspace '{workspace_id}' not found"
                )

            return ToolResult(
                success=True,
                data={
                    "workspace": state,
                    "document_count": len(state.get("documents", [])),
                    "rule_count": len(state.get("rules", [])),
                    "exclusion_count": len(state.get("exclusions", []))
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get workspace state: {str(e)}")


class CreateRuleTool(Tool):
    """Create a new redaction rule in workspace."""

    name = "create_rule"
    description = "Create a new redaction rule for a category in the workspace."

    def __init__(self, workspace_service=None, rule_engine=None):
        self.workspace_service = workspace_service
        self.rule_engine = rule_engine

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier"
                },
                "category": {
                    "type": "string",
                    "description": "Redaction category (e.g., 'PII', 'CreditCard')"
                },
                "pattern": {
                    "type": "string",
                    "description": "Pattern or description for what to redact"
                }
            },
            "required": ["workspace_id", "category", "pattern"]
        }

    async def execute(self, workspace_id: str, category: str, pattern: str, **kwargs) -> ToolResult:
        """Create a new rule."""
        if not self.workspace_service:
            return ToolResult(success=False, error="Workspace service not configured")

        try:
            result = await self.workspace_service.create_workspace_rule(
                workspace_id,
                {"category": category, "pattern": pattern}
            )
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create rule: {str(e)}")


class ApplyRuleTool(Tool):
    """Apply a saved rule across documents in workspace."""

    name = "apply_rule"
    description = "Apply a saved workspace rule across non-excluded documents."

    def __init__(self, workspace_service=None):
        self.workspace_service = workspace_service

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier"
                },
                "rule_id": {
                    "type": "string",
                    "description": "Workspace rule identifier"
                }
            },
            "required": ["workspace_id", "rule_id"]
        }

    async def execute(self, workspace_id: str, rule_id: str, **kwargs) -> ToolResult:
        """Apply a rule."""
        if not self.workspace_service:
            return ToolResult(success=False, error="Workspace service not configured")

        try:
            result = await self.workspace_service.apply_batch_rule(workspace_id, rule_id)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to apply rule: {str(e)}")


class ExcludeDocumentTool(Tool):
    """Exclude a document from workspace automation."""

    name = "exclude_document"
    description = "Exclude a document from workspace rules and automation."

    def __init__(self, workspace_service=None):
        self.workspace_service = workspace_service

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Workspace identifier"
                },
                "document_id": {
                    "type": "string",
                    "description": "Document to exclude"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for exclusion"
                }
            },
            "required": ["workspace_id", "document_id"]
        }

    async def execute(self, workspace_id: str, document_id: str, reason: str = "Excluded from automation", **kwargs) -> ToolResult:
        """Exclude document."""
        if not self.workspace_service:
            return ToolResult(success=False, error="Workspace service not configured")

        try:
            result = await self.workspace_service.exclude_document(workspace_id, document_id, reason)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to exclude document: {str(e)}")
