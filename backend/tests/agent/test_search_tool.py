import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from redactor.agent.tools.search import DocumentTools
from redactor.models import Suggestion, RedactionRect
from datetime import datetime


def make_suggestion(text="test data", category="PII"):
    return Suggestion(
        id="s1",
        job_id="job1",
        text=text,
        category=category,
        reasoning="Found test",
        context=f"This is {text}",
        page_num=0,
        rects=[RedactionRect(x0=0, y0=0, x1=1, y1=1)],
        approved=False,
        source="ai",
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_search_document_finds_text():
    """search_document returns JSON with matching suggestions."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("test data")]
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="test", doc_id="job1")
    data = json.loads(result)
    assert data["count"] == 1
    assert "test" in data["results"][0]["text"]


@pytest.mark.asyncio
async def test_search_document_returns_empty_when_no_match():
    """search_document returns zero results when nothing matches."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("unrelated content")]
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="zzznomatch", doc_id="job1")
    data = json.loads(result)
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_search_document_returns_error_for_missing_job():
    """search_document returns error string when job not found."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = None
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="test", doc_id="missing")
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_search_document_returns_error_when_service_missing():
    """search_document returns error string when service is not configured."""
    tools = DocumentTools(job_service=None)
    result = await tools.search_document(query="test", doc_id="doc1")
    assert "not configured" in result.lower()


@pytest.mark.asyncio
async def test_search_document_returns_error_for_empty_query():
    """search_document returns error string when query is empty."""
    mock_job_service = AsyncMock()
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="", doc_id="doc1")
    assert "empty" in result.lower()
