import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from redactor.main import app
from redactor.models import Job, JobStatus, Suggestion, RedactionRect
from redactor.routes import jobs as jobs_module

@pytest.fixture(autouse=True)
def seed_job():
    suggestion = Suggestion(
        id="s1", text="John Smith", category="Person",
        reasoning="PII", context="", page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)]
    )
    jobs_module._jobs["job-test"] = Job(
        job_id="job-test", status=JobStatus.COMPLETE, suggestions=[suggestion]
    )
    yield
    jobs_module._jobs.pop("job-test", None)

@pytest.mark.asyncio
async def test_toggle_suggestion_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": False}
        )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_toggle_suggestion_approval_sets_value():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": False}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["approved"] is False
    assert data["id"] == "s1"

@pytest.mark.asyncio
async def test_toggle_suggestion_unknown_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/no-such-job/redactions/s1",
            json={"approved": False}
        )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_toggle_suggestion_unknown_suggestion():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/no-such-suggestion",
            json={"approved": False}
        )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_add_manual_redaction():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/jobs/job-test/redactions/manual",
            json={"page_num": 1, "rects": [{"x0": 5, "y0": 5, "x1": 50, "y1": 20}]}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Manual"
    assert data["approved"] is True
    assert data["source"] == "manual"

@pytest.mark.asyncio
async def test_apply_redactions_returns_pdf():
    mock_blob = MagicMock()
    mock_blob.download_original_pdf = AsyncMock(return_value=b"%PDF")
    mock_blob.save_redacted_pdf = AsyncMock()
    app.state.blob_client = mock_blob
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_apply_redactions_response_body():
    mock_blob = MagicMock()
    mock_blob.download_original_pdf = AsyncMock(return_value=b"%PDF")
    mock_blob.save_redacted_pdf = AsyncMock()
    app.state.blob_client = mock_blob
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")
    data = response.json()
    assert data["status"] == "applied"
    assert data["redaction_count"] == 1  # seed has 1 approved suggestion

@pytest.mark.asyncio
async def test_apply_redactions_job_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/jobs/no-such-job/redactions/apply")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_apply_redactions_job_not_complete():
    from redactor.models import Job, JobStatus
    jobs_module._jobs["job-pending"] = Job(job_id="job-pending", status=JobStatus.PROCESSING)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-pending/redactions/apply")
        assert response.status_code == 400
    finally:
        jobs_module._jobs.pop("job-pending", None)

@pytest.mark.asyncio
async def test_apply_redactions_with_none_approved():
    # Toggle s1 to unapproved first
    jobs_module._jobs["job-test"].suggestions[0].approved = False
    mock_blob = MagicMock()
    mock_blob.download_original_pdf = AsyncMock(return_value=b"%PDF")
    mock_blob.save_redacted_pdf = AsyncMock()
    app.state.blob_client = mock_blob
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-empty"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")
    assert response.status_code == 200
    assert response.json()["redaction_count"] == 0
