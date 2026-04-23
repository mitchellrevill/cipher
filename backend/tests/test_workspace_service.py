from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.workspace_service import WorkspaceService
from app.services.job_service import JobService


def make_containers():
    def container():
        instance = MagicMock()
        instance.create_item = MagicMock()
        instance.read_item = MagicMock()
        instance.replace_item = MagicMock()
        instance.query_items = MagicMock(return_value=[])
        instance.delete_item = MagicMock()
        return instance

    return container(), container(), container()


def make_workspace(ws_id="ws_1", doc_ids=None, rule_ids=None, excl_ids=None):
    now = datetime.utcnow().isoformat()
    return {
        "id": ws_id,
        "user_id": "user_1",
        "name": "Workspace",
        "description": None,
        "document_ids": doc_ids or [],
        "rule_ids": rule_ids or [],
        "exclusion_ids": excl_ids or [],
        "created_at": now,
        "updated_at": now,
        "type": "workspace",
    }


@pytest.mark.asyncio
async def test_create_workspace():
    ws_c, rules_c, excl_c = make_containers()
    ws_c.create_item.return_value = make_workspace()
    service = WorkspaceService(ws_c, rules_c, excl_c)

    workspace = await service.create_workspace(user_id="user_123", name="Test Workspace")

    assert workspace["id"].startswith("ws_")
    ws_c.create_item.assert_called_once()


@pytest.mark.asyncio
async def test_assign_job_updates_both_sides():
    ws_c, rules_c, excl_c = make_containers()
    ws_c.read_item.return_value = make_workspace(doc_ids=[])
    ws_c.replace_item.side_effect = lambda item, body: body
    service = WorkspaceService(ws_c, rules_c, excl_c)
    mock_job_service = AsyncMock(spec=JobService)

    workspace = await service.assign_job("ws_1", "job-1", mock_job_service)

    assert "job-1" in workspace["document_ids"]
    mock_job_service.update_workspace_id.assert_called_once_with("job-1", "ws_1")


@pytest.mark.asyncio
async def test_assign_job_rolls_back_if_job_update_fails():
    ws_c, rules_c, excl_c = make_containers()
    workspace = make_workspace(doc_ids=[])
    ws_c.read_item.side_effect = [workspace.copy(), {**workspace, "document_ids": ["job-1"]}, workspace.copy()]
    ws_c.replace_item.side_effect = lambda item, body: body
    service = WorkspaceService(ws_c, rules_c, excl_c)
    mock_job_service = AsyncMock(spec=JobService)
    mock_job_service.update_workspace_id.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await service.assign_job("ws_1", "job-1", mock_job_service)

    rollback_body = ws_c.replace_item.call_args_list[-1].kwargs["body"]
    assert "job-1" not in rollback_body["document_ids"]


@pytest.mark.asyncio
async def test_remove_job_clears_both_sides():
    ws_c, rules_c, excl_c = make_containers()
    ws_c.read_item.side_effect = [make_workspace(doc_ids=["job-1"]), make_workspace(doc_ids=[])]
    ws_c.replace_item.side_effect = lambda item, body: body
    service = WorkspaceService(ws_c, rules_c, excl_c)
    mock_job_service = AsyncMock(spec=JobService)

    workspace = await service.remove_job("ws_1", "job-1", mock_job_service)

    assert "job-1" not in workspace["document_ids"]
    mock_job_service.update_workspace_id.assert_called_once_with("job-1", None)


@pytest.mark.asyncio
async def test_create_rule_stores_in_rules_container():
    ws_c, rules_c, excl_c = make_containers()
    ws_c.read_item.return_value = make_workspace(rule_ids=[])
    ws_c.replace_item.side_effect = lambda item, body: body
    rules_c.create_item.return_value = {
        "id": "rule_1",
        "workspace_id": "ws_1",
        "pattern": "secret",
        "category": "PII",
        "confidence_threshold": 0.8,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "type": "workspace_rule",
    }
    service = WorkspaceService(ws_c, rules_c, excl_c)

    await service.create_rule(workspace_id="ws_1", pattern="secret", category="PII")

    replaced = ws_c.replace_item.call_args.kwargs["body"]
    assert "rule_1" in replaced["rule_ids"]


@pytest.mark.asyncio
async def test_get_workspace_not_found_returns_none():
    ws_c, rules_c, excl_c = make_containers()
    ws_c.read_item.side_effect = Exception("missing")
    ws_c.query_items.return_value = []
    service = WorkspaceService(ws_c, rules_c, excl_c)

    result = await service.get_workspace("missing")

    assert result is None


@pytest.mark.asyncio
async def test_get_workspace_falls_back_to_query_when_partition_key_differs():
    ws_c, rules_c, excl_c = make_containers()
    ws_c.read_item.side_effect = Exception("wrong partition key")
    ws_c.query_items.return_value = [make_workspace(ws_id="ws_live")]
    service = WorkspaceService(ws_c, rules_c, excl_c)

    result = await service.get_workspace("ws_live")

    assert result is not None
    assert result["id"] == "ws_live"
    assert ws_c.query_items.called
