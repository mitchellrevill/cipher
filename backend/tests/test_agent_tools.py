import pytest
import uuid
from redactor.agent.tools import make_tools
from redactor.models import Job, JobStatus, Suggestion, RedactionRect
from redactor.routes import jobs as jobs_module

@pytest.fixture
def seeded_job():
    from datetime import datetime
    job_id = str(uuid.uuid4())
    s = Suggestion(id="s1", job_id=job_id, text="John", category="Person", reasoning="", context="",
                   page_num=0, rects=[RedactionRect(x0=0,y0=0,x1=10,y1=10)], approved=True, created_at=datetime.utcnow())
    jobs_module._jobs[job_id] = Job(job_id=job_id, status=JobStatus.COMPLETE, suggestions=[s])
    yield job_id
    jobs_module._jobs.pop(job_id, None)

def test_get_redaction_summary(seeded_job):
    tools = make_tools(seeded_job)
    summary = tools["get_redaction_summary"]()
    assert summary["total_approved"] == 1
    assert "Person" in summary["by_category"]

def test_remove_redaction(seeded_job):
    tools = make_tools(seeded_job)
    result = tools["remove_redaction"]("s1")
    assert "removed" in result
    assert len(jobs_module._jobs[seeded_job].suggestions) == 0

def test_add_exception_removes_matching_suggestions(seeded_job):
    tools = make_tools(seeded_job)
    result = tools["add_exception"]("John")
    assert "exception" in result.lower()
    job = jobs_module._jobs[seeded_job]
    remaining = [s for s in job.suggestions if s.approved]
    assert len(remaining) == 0

def test_search_document(seeded_job):
    tools = make_tools(seeded_job)
    results = tools["search_document"]("John")
    assert len(results) >= 1
