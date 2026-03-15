"""Tests for redactions routes."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from datetime import datetime
from redactor.models import Job, JobStatus, Suggestion, RedactionRect


# Note: All service and container mocks are now defined in conftest.py
# The completed_job_with_suggestions and sample_suggestion fixtures are available

@pytest.fixture
def seeded_job():
    """Create a test job with suggestions for testing."""
    suggestion = Suggestion(
        id="s1", job_id="job-test", text="John Smith", category="Person",
        reasoning="PII", context="", page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)], approved=True, created_at=datetime.utcnow()
    )
    return Job(
        job_id="job-test", status=JobStatus.COMPLETE, suggestions=[suggestion], user_id="test-user-123"
    )


@pytest.fixture(autouse=True)
def seed_job_service(mock_job_service, seeded_job):
    """Seed the shared mocked job service with a known completed job."""

    async def get_job_side_effect(job_id: str):
        if job_id == "job-test":
            return seeded_job
        return None

    mock_job_service.get_job.side_effect = get_job_side_effect
    return mock_job_service

@pytest.mark.asyncio
async def test_toggle_suggestion_approval(test_app, mock_redaction_service):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": False}
        )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_toggle_suggestion_approval_sets_value(test_app, mock_redaction_service):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": False}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["approved"] is False
    assert data["id"] == "s1"

@pytest.mark.asyncio
async def test_toggle_suggestion_unknown_job(test_app, mock_redaction_service):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/no-such-job/redactions/s1",
            json={"approved": False}
        )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_toggle_suggestion_unknown_suggestion(test_app, mock_redaction_service):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/no-such-suggestion",
            json={"approved": False}
        )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_approve_all_suggestions_updates_unapproved_items(test_app, mock_redaction_service, seeded_job):
    seeded_job.suggestions.extend([
        Suggestion(
            id="s2", job_id="job-test", text="Jane Smith", category="Person",
            reasoning="PII", context="", page_num=1,
            rects=[RedactionRect(x0=20, y0=20, x1=110, y1=40)], approved=False, created_at=datetime.utcnow()
        ),
        Suggestion(
            id="s3", job_id="job-test", text="Account 1234", category="Financial",
            reasoning="Sensitive", context="", page_num=2,
            rects=[RedactionRect(x0=30, y0=30, x1=120, y1=50)], approved=False, created_at=datetime.utcnow()
        ),
    ])
    mock_redaction_service.bulk_update_approvals.return_value = 2

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/jobs/job-test/redactions/approve-all")

    assert response.status_code == 200
    assert response.json() == {"approved": True, "updated_count": 2}
    assert all(s.approved for s in seeded_job.suggestions)
    mock_redaction_service.bulk_update_approvals.assert_awaited_once_with("job-test", True)

@pytest.mark.asyncio
async def test_approve_all_suggestions_handles_unknown_job(test_app, mock_redaction_service):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/jobs/no-such-job/redactions/approve-all")

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_add_manual_redaction(test_app, mock_redaction_service):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
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
async def test_apply_redactions_returns_pdf(test_app, mock_blob_client):
    with patch("redactor.routes.redactions._get_blob", return_value=mock_blob_client), patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_apply_redactions_response_body(test_app, mock_blob_client):
    with patch("redactor.routes.redactions._get_blob", return_value=mock_blob_client), patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")
    data = response.json()
    assert data["status"] == "applied"
    assert data["redaction_count"] == 1  # seed has 1 approved suggestion

@pytest.mark.asyncio
async def test_apply_redactions_job_not_found(test_app, mock_redaction_service):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/jobs/no-such-job/redactions/apply")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_apply_redactions_job_not_complete(test_app, mock_redaction_service):
    # The test_app fixture uses seeded_job_service which returns job-test (COMPLETE status)
    # For this test, we need to use a job with PROCESSING status
    # Since the seeded_job_service is hardcoded to job-test, we'll update its return value
    pending_job = Job(job_id="job-test", status=JobStatus.PROCESSING, user_id="test-user-123")
    test_app.container.job_service.return_value.get_job = AsyncMock(return_value=pending_job)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/jobs/job-test/redactions/apply")
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_apply_redactions_with_none_approved(test_app, mock_blob_client, seeded_job):
    # Toggle s1 to unapproved first
    seeded_job.suggestions[0].approved = False
    with patch("redactor.routes.redactions._get_blob", return_value=mock_blob_client), patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-empty"
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")
    assert response.status_code == 200
    assert response.json()["redaction_count"] == 0
