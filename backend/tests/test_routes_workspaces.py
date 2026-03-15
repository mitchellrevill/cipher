from httpx import ASGITransport, AsyncClient
import pytest


@pytest.mark.asyncio
async def test_create_workspace(mock_workspace_service, test_app):
    mock_workspace_service.create_workspace.return_value = {
        "id": "ws_test",
        "name": "Test Workspace",
        "document_ids": [],
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/workspaces", json={"name": "Test Workspace"})

    assert response.status_code == 201
    assert response.json()["name"] == "Test Workspace"


@pytest.mark.asyncio
async def test_list_workspaces(mock_workspace_service, test_app):
    mock_workspace_service.list_workspaces.return_value = [{"id": "ws_test", "name": "Test Workspace"}]

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/workspaces")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_add_document_to_workspace(mock_workspace_service, test_app):
    mock_workspace_service.assign_job.return_value = {
        "id": "ws_test",
        "document_ids": ["doc_123"],
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            "/api/workspaces/ws_test/documents",
            json={"document_id": "doc_123"},
        )

    assert response.status_code == 200
    assert "doc_123" in response.json()["document_ids"]
    mock_workspace_service.assign_job.assert_called_once()
