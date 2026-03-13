import json
import pytest
from unittest.mock import AsyncMock
from redactor.agent.tools.workspace import WorkspaceTools


def make_workspace_service(state=None):
    service = AsyncMock()
    service.get_workspace_state.return_value = state or {
        "id": "ws1",
        "name": "Test Workspace",
        "documents": [{"id": "d1"}],
        "rules": [{"id": "r1", "category": "PII", "pattern": "SSN"}],
        "exclusions": [],
    }
    service.create_workspace_rule.return_value = {"id": "rule-new", "category": "CreditCard"}
    service.apply_batch_rule.return_value = {"applied": 3}
    service.exclude_document.return_value = {"excluded": True}
    return service


@pytest.mark.asyncio
async def test_get_workspace_state_returns_json():
    """get_workspace_state returns JSON string with workspace data."""
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.get_workspace_state(workspace_id="ws1")
    data = json.loads(result)
    assert data["document_count"] == 1
    assert data["rule_count"] == 1


@pytest.mark.asyncio
async def test_get_workspace_state_returns_error_for_missing():
    """get_workspace_state returns error string when workspace not found."""
    service = make_workspace_service(state=None)
    service.get_workspace_state.return_value = None
    tools = WorkspaceTools(workspace_service=service)
    result = await tools.get_workspace_state(workspace_id="missing")
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_create_rule_returns_json():
    """create_rule returns JSON confirmation string."""
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.create_rule(workspace_id="ws1", category="CreditCard", pattern="4[0-9]{15}")
    data = json.loads(result)
    assert "id" in data


@pytest.mark.asyncio
async def test_apply_rule_returns_json():
    """apply_rule returns JSON with applied count."""
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.apply_rule(workspace_id="ws1", rule_id="r1")
    data = json.loads(result)
    assert "applied" in data


@pytest.mark.asyncio
async def test_exclude_document_returns_json():
    """exclude_document returns JSON confirmation."""
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.exclude_document(workspace_id="ws1", document_id="d1", reason="Exempt")
    data = json.loads(result)
    assert "excluded" in data


@pytest.mark.asyncio
async def test_workspace_tools_return_error_when_service_missing():
    """All tools return error string when workspace_service is None."""
    tools = WorkspaceTools(workspace_service=None)
    for coro in [
        tools.get_workspace_state(workspace_id="ws1"),
        tools.create_rule(workspace_id="ws1", category="PII", pattern=".*"),
        tools.apply_rule(workspace_id="ws1", rule_id="r1"),
        tools.exclude_document(workspace_id="ws1", document_id="d1"),
    ]:
        result = await coro
        assert "not configured" in result.lower()
