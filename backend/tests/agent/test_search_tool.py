import pytest
from redactor.agent.tools.search import SearchTool
from redactor.agent.tools.base import ToolResult


class MockWorkspaceToolbox:
    async def search_document(self, query: str, doc_id: str = None, workspace_id: str = None):
        if query == "not found":
            return []
        return [
            {
                "document_id": doc_id or "doc1",
                "page": 1,
                "text": f"Found: {query}",
                "coords": [[10, 20, 30, 40]]
            }
        ]


@pytest.mark.asyncio
async def test_search_tool_finds_text():
    """Search tool should find matching text in documents."""
    toolbox = MockWorkspaceToolbox()
    tool = SearchTool(workspace_toolbox=toolbox)

    result = await tool.execute(query="test", doc_id="doc1")

    assert result.success
    assert len(result.data["results"]) == 1
    assert "test" in result.data["results"][0]["text"]


@pytest.mark.asyncio
async def test_search_tool_returns_no_results():
    """Search tool should return empty results when nothing found."""
    toolbox = MockWorkspaceToolbox()
    tool = SearchTool(workspace_toolbox=toolbox)

    result = await tool.execute(query="not found")

    assert result.success
    assert result.data["results"] == []


def test_search_tool_has_correct_schema():
    """Search tool schema should define query parameter."""
    tool = SearchTool(workspace_toolbox=None)
    schema = tool.schema

    assert "query" in schema["properties"]
    assert "query" in schema["required"]
