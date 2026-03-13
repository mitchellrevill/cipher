import pytest
from unittest.mock import AsyncMock, MagicMock
from redactor.agent.tools.search import SearchTool
from redactor.agent.tools.base import ToolResult
from redactor.models import Suggestion, RedactionRect
from datetime import datetime


@pytest.mark.asyncio
async def test_search_tool_finds_text():
    """Search tool should find matching text in documents."""
    mock_job_service = AsyncMock()
    suggestion = Suggestion(
        id="s1",
        job_id="job1",
        text="test data",
        category="PII",
        reasoning="Found test",
        context="This is test data",
        page_num=0,
        rects=[RedactionRect(x0=0, y0=0, x1=1, y1=1)],
        approved=False,
        source="ai",
        created_at=datetime.utcnow(),
    )
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        filename="test.pdf",
        suggestions=[suggestion]
    )

    tool = SearchTool(job_service=mock_job_service)
    result = await tool.execute(query="test", doc_id="job1")

    assert result.success
    assert len(result.data["results"]) == 1
    assert "test" in result.data["results"][0]["text"]


@pytest.mark.asyncio
async def test_search_tool_returns_no_results():
    """Search tool should return empty results when nothing found."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        filename="test.pdf",
        suggestions=[]
    )

    tool = SearchTool(job_service=mock_job_service)
    result = await tool.execute(query="not found", doc_id="job1")

    assert result.success
    assert result.data["results"] == []


def test_search_tool_has_correct_schema():
    """Search tool schema should define query and doc_id parameters."""
    tool = SearchTool(job_service=None)
    schema = tool.schema

    assert "query" in schema["properties"]
    assert "doc_id" in schema["properties"]
    assert "query" in schema["required"]
    assert "doc_id" in schema["required"]
