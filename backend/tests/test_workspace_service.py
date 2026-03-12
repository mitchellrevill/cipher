from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from redactor.services.workspace_service import WorkspaceService


@pytest.fixture
def workspace_service():
    mock_cosmos = AsyncMock()
    return WorkspaceService(cosmos_client=mock_cosmos)


@pytest.mark.asyncio
async def test_create_workspace(workspace_service):
    workspace_service.cosmos_client.create_item = AsyncMock(
        return_value={
            "id": "ws_test",
            "user_id": "user_123",
            "name": "Test Workspace",
            "document_ids": [],
            "created_at": datetime.utcnow().isoformat(),
        }
    )

    workspace = await workspace_service.create_workspace(user_id="user_123", name="Test Workspace")

    assert workspace["name"] == "Test Workspace"
    assert workspace["user_id"] == "user_123"
    workspace_service.cosmos_client.create_item.assert_called_once()


@pytest.mark.asyncio
async def test_get_workspace(workspace_service):
    workspace_service.cosmos_client.read_item = AsyncMock(
        return_value={
            "id": "ws_test",
            "name": "Test Workspace",
        }
    )

    workspace = await workspace_service.get_workspace("ws_test")

    assert workspace["id"] == "ws_test"
    workspace_service.cosmos_client.read_item.assert_called_once()


@pytest.mark.asyncio
async def test_add_document_to_workspace(workspace_service):
    workspace_service.cosmos_client.read_item = AsyncMock(
        return_value={
            "id": "ws_test",
            "document_ids": ["doc_1"],
            "rule_ids": [],
            "exclusion_ids": [],
        }
    )
    workspace_service.cosmos_client.upsert_item = AsyncMock(
        return_value={
            "id": "ws_test",
            "document_ids": ["doc_1", "doc_2"],
        }
    )

    updated = await workspace_service.add_document("ws_test", "doc_2")

    assert "doc_2" in updated["document_ids"]
    workspace_service.cosmos_client.upsert_item.assert_called_once()
