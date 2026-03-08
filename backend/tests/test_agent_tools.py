from redactor.agent.tools import make_tools
from redactor.models import Job, JobStatus, Suggestion, RedactionRect
from redactor.routes import jobs as jobs_module

def _seed_job(job_id="j1"):
    s = Suggestion(id="s1", text="John", category="Person", reasoning="", context="",
                   page_num=0, rects=[RedactionRect(x0=0,y0=0,x1=10,y1=10)], approved=True)
    jobs_module._jobs[job_id] = Job(job_id=job_id, status=JobStatus.COMPLETE, suggestions=[s])
    return job_id

def test_get_redaction_summary():
    job_id = _seed_job()
    tools = make_tools(job_id)
    summary = tools["get_redaction_summary"]()
    assert summary["total_approved"] == 1
    assert "Person" in summary["by_category"]

def test_remove_redaction():
    job_id = _seed_job()
    tools = make_tools(job_id)
    result = tools["remove_redaction"]("s1")
    assert "removed" in result
    assert len(jobs_module._jobs[job_id].suggestions) == 0

def test_add_exception_removes_matching_suggestions():
    job_id = _seed_job()
    tools = make_tools(job_id)
    result = tools["add_exception"]("John")
    assert "exception" in result.lower()
    job = jobs_module._jobs[job_id]
    remaining = [s for s in job.suggestions if s.approved]
    assert len(remaining) == 0

def test_search_document():
    job_id = _seed_job()
    tools = make_tools(job_id)
    results = tools["search_document"]("John")
    assert len(results) >= 1
