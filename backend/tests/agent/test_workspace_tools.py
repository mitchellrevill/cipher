import json
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from redactor.agent.tools.workspace import WorkspaceTools
from redactor.models import Suggestion, RedactionRect
from datetime import datetime


def make_suggestion(text="123-45-6789", suggestion_id="s1"):
    return Suggestion(
        id=suggestion_id,
        job_id="job1",
        text=text,
        category="PII",
        reasoning="Found test",
        context=f"This is {text}",
        page_num=1,
        rects=[RedactionRect(x0=0, y0=0, x1=1, y1=1)],
        approved=False,
        source="ai",
        created_at=datetime.utcnow(),
    )


def make_workspace_service(state=None):
    service = AsyncMock()
    service.get_workspace_state.return_value = state or {
        "id": "ws1",
        "name": "Test Workspace",
        "documents": [{"id": "d1"}],
        "rules": [{"id": "r1", "category": "PII", "pattern": "SSN"}],
        "exclusions": [],
    }
    service.create_rule.return_value = {"id": "rule-new", "category": "CreditCard"}
    service.get_rules.return_value = [{"id": "r1", "category": "PII", "pattern": r"\b\d{3}-\d{2}-\d{4}\b"}]
    service.get_exclusions.return_value = []
    service.exclude_document.return_value = {"excluded": True}
    service.add_document.return_value = {"id": "ws1", "document_ids": ["d1", "d2"]}
    service.remove_document.return_value = {"id": "ws1", "document_ids": ["d1"]}
    service.remove_exclusion.return_value = {"id": "ws1", "exclusion_ids": []}
    return service


def make_job_service():
    service = AsyncMock()
    service.get_job.return_value = SimpleNamespace(
        job_id="d1",
        suggestions=[make_suggestion()],
    )
    return service


def make_redaction_service():
    service = AsyncMock()
    service.bulk_update_approvals.return_value = 1
    return service


def make_rule_engine():
    engine = AsyncMock()
    engine.apply_rule.return_value = {"applied_count": 1, "affected_docs": [{"document_id": "d1"}]}
    return engine


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
    tools = WorkspaceTools(
        workspace_service=make_workspace_service(),
        job_service=make_job_service(),
        redaction_service=make_redaction_service(),
        rule_engine=make_rule_engine(),
    )
    result = await tools.apply_rule(workspace_id="ws1", rule_id="r1")
    data = json.loads(result)
    assert "applied_count" in data


@pytest.mark.asyncio
async def test_exclude_document_returns_json():
    """exclude_document returns JSON confirmation."""
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.exclude_document(workspace_id="ws1", document_id="d1", reason="Exempt")
    data = json.loads(result)
    assert "excluded" in data


@pytest.mark.asyncio
async def test_list_workspace_rules_returns_json():
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.list_workspace_rules(workspace_id="ws1")
    data = json.loads(result)
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_list_workspace_exclusions_returns_json():
    service = make_workspace_service()
    service.get_exclusions.return_value = [{"id": "ex1", "document_id": "d1"}]
    tools = WorkspaceTools(workspace_service=service)
    result = await tools.list_workspace_exclusions(workspace_id="ws1")
    data = json.loads(result)
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_add_and_remove_document_tools_return_json():
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    added = json.loads(await tools.add_document_to_workspace(workspace_id="ws1", document_id="d2"))
    removed = json.loads(await tools.remove_document_from_workspace(workspace_id="ws1", document_id="d2"))
    assert added["id"] == "ws1"
    assert removed["id"] == "ws1"


@pytest.mark.asyncio
async def test_remove_exclusion_returns_json():
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.remove_exclusion(workspace_id="ws1", exclusion_id="ex1")
    data = json.loads(result)
    assert data["id"] == "ws1"


@pytest.mark.asyncio
async def test_workspace_tools_return_error_when_service_missing():
    """All tools return error string when workspace_service is None."""
    tools = WorkspaceTools(workspace_service=None)
    for coro in [
        tools.get_workspace_state(workspace_id="ws1"),
        tools.create_rule(workspace_id="ws1", category="PII", pattern=".*"),
        tools.apply_rule(workspace_id="ws1", rule_id="r1"),
        tools.exclude_document(workspace_id="ws1", document_id="d1"),
        tools.list_workspace_rules(workspace_id="ws1"),
        tools.list_workspace_exclusions(workspace_id="ws1"),
        tools.add_document_to_workspace(workspace_id="ws1", document_id="d1"),
        tools.remove_document_from_workspace(workspace_id="ws1", document_id="d1"),
        tools.remove_exclusion(workspace_id="ws1", exclusion_id="ex1"),
    ]:
        result = await coro
        assert "not configured" in result.lower()


@pytest.mark.asyncio
async def test_apply_rule_returns_error_when_dependencies_missing():
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.apply_rule(workspace_id="ws1", rule_id="r1")
    assert "not configured" in result.lower()
