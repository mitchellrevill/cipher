import pytest
from redactor.agent.tools.workspace import (
    GetWorkspaceStateTool,
    CreateRuleTool,
    ApplyRuleTool,
    ExcludeDocumentTool
)


class MockWorkspaceService:
    async def get_workspace_state(self, workspace_id: str):
        if workspace_id == "missing":
            return None
        return {
            "id": workspace_id,
            "name": "Test Workspace",
            "documents": [{"id": "doc1", "filename": "test.pdf"}],
            "rules": [{"id": "rule1", "category": "PII", "pattern": "SSN"}],
            "exclusions": []
        }


@pytest.mark.asyncio
async def test_get_workspace_state_tool():
    """GetWorkspaceStateTool should return workspace context."""
    service = MockWorkspaceService()
    tool = GetWorkspaceStateTool(workspace_service=service)

    result = await tool.execute(workspace_id="ws123")

    assert result.success
    assert result.data["workspace"]["name"] == "Test Workspace"


@pytest.mark.asyncio
async def test_get_workspace_state_returns_error_for_missing():
    """Should return error for missing workspace."""
    service = MockWorkspaceService()
    tool = GetWorkspaceStateTool(workspace_service=service)

    result = await tool.execute(workspace_id="missing")

    assert not result.success
    assert "not found" in result.error.lower()


def test_workspace_tools_have_correct_schemas():
    """All workspace tools should have proper schemas."""
    tools = [
        GetWorkspaceStateTool(workspace_service=None),
        CreateRuleTool(workspace_service=None),
    ]

    for tool in tools:
        schema = tool.schema
        assert schema["type"] == "object"
        assert "properties" in schema
