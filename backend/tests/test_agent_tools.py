import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from redactor.agent.tools import make_tools
from redactor.models import Job, JobStatus, Suggestion, RedactionRect


@pytest.fixture
def mock_job_service():
    """Create a mock JobService."""
    job_service = AsyncMock()
    return job_service


@pytest.fixture
async def seeded_job_and_service():
    """Create a seeded job with mock JobService for testing."""
    from datetime import datetime
    job_id = str(uuid.uuid4())
    s = Suggestion(
        id="s1", job_id=job_id, text="John", category="Person",
        reasoning="", context="", page_num=0,
        rects=[RedactionRect(x0=0, y0=0, x1=10, y1=10)],
        approved=True, created_at=datetime.utcnow()
    )
    job = Job(job_id=job_id, status=JobStatus.COMPLETE, suggestions=[s])

    job_service = AsyncMock()
    job_service.get_job = AsyncMock(return_value=job)

    yield job_id, job_service, job


@pytest.mark.asyncio
async def test_get_redaction_summary(seeded_job_and_service):
    job_id, job_service, job = seeded_job_and_service
    tools = make_tools(job_id, job_service)
    summary = await tools["get_redaction_summary"]()
    assert summary["total_approved"] == 1
    assert "Person" in summary["by_category"]


@pytest.mark.asyncio
async def test_remove_redaction(seeded_job_and_service):
    job_id, job_service, job = seeded_job_and_service
    tools = make_tools(job_id, job_service)
    result = await tools["remove_redaction"]("s1")
    assert "removed" in result
    assert len(job.suggestions) == 0


@pytest.mark.asyncio
async def test_add_exception_removes_matching_suggestions(seeded_job_and_service):
    job_id, job_service, job = seeded_job_and_service
    tools = make_tools(job_id, job_service)
    result = await tools["add_exception"]("John")
    assert "exception" in result.lower()
    remaining = [s for s in job.suggestions if s.approved]
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_search_document(seeded_job_and_service):
    job_id, job_service, job = seeded_job_and_service
    tools = make_tools(job_id, job_service)
    results = await tools["search_document"]("John")
    assert len(results) >= 1
