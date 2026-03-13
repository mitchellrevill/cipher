import pytest
from redactor.agent.knowledge_base import KnowledgeBase


@pytest.mark.asyncio
async def test_knowledge_base_loads_workspace_context():
    """Knowledge base should load and cache workspace context."""
    # Mock workspace service
    class MockWorkspaceService:
        async def get_workspace_state(self, workspace_id: str):
            return {
                "id": workspace_id,
                "name": "Test Workspace",
                "documents": [{"id": "doc1", "filename": "test.pdf"}],
                "rules": [],
                "exclusions": []
            }

    kb = KnowledgeBase(workspace_service=MockWorkspaceService())
    context = await kb.get_workspace_context("ws123")

    assert context["name"] == "Test Workspace"
    assert len(context["documents"]) == 1


@pytest.mark.asyncio
async def test_knowledge_base_returns_none_for_missing_workspace():
    """Knowledge base returns None for workspace that doesn't exist."""
    class MockWorkspaceService:
        async def get_workspace_state(self, workspace_id: str):
            return None

    kb = KnowledgeBase(workspace_service=MockWorkspaceService())
    context = await kb.get_workspace_context("missing")

    assert context is None


@pytest.mark.asyncio
async def test_knowledge_base_caches_context():
    """Knowledge base should cache context to avoid repeated lookups."""
    call_count = 0

    class MockWorkspaceService:
        async def get_workspace_state(self, workspace_id: str):
            nonlocal call_count
            call_count += 1
            return {"id": workspace_id, "name": f"Workspace {call_count}"}

    kb = KnowledgeBase(workspace_service=MockWorkspaceService())

    context1 = await kb.get_workspace_context("ws123")
    context2 = await kb.get_workspace_context("ws123")

    assert context1 == context2
    assert call_count == 1  # Should only call service once
