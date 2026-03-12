"""Tests for redactions route using RedactionService dependency injection."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from redactor.models import Job, JobStatus, Suggestion, RedactionRect
from redactor.services.redaction_service import RedactionService
from redactor.services.job_service import JobService


# Note: All service and container mocks are now defined in conftest.py
# The completed_job_with_suggestions and sample_suggestion fixtures are available

@pytest.fixture
def seeded_job():
    """Create a test job with suggestions for testing."""
    suggestion = Suggestion(
        id="s1", job_id="job-test", text="John Smith", category="Person",
        reasoning="PII", context="", page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)],
        approved=True, created_at=datetime.utcnow()
    )
    return Job(
        job_id="job-test", status=JobStatus.COMPLETE, suggestions=[suggestion]
    )


@pytest.fixture
def seeded_job_service():
    """
    Create a mock JobService with a seeded job for redactions testing.

    This provides a job with ID "job-test" and one suggestion for testing.
    """
    suggestion = Suggestion(
        id="s1", job_id="job-test", text="John Smith", category="Person",
        reasoning="PII", context="", page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)],
        approved=True, created_at=datetime.utcnow()
    )
    seeded_job = Job(
        job_id="job-test", status=JobStatus.COMPLETE, suggestions=[suggestion]
    )

    service = MagicMock(spec=JobService)

    async def get_job_side_effect(job_id: str):
        """Return seeded job for known job_id, None otherwise."""
        if job_id == "job-test":
            return seeded_job
        return None

    service.get_job = AsyncMock(side_effect=get_job_side_effect)
    return service


@pytest.fixture
def test_app_redactions_service(seeded_job_service, mock_redaction_service, mock_blob_client):
    """Create a test FastAPI app for redactions route with seeded job data."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from redactor.routes import redactions
    from redactor.config import get_settings
    from redactor.containers.app import AppContainer

    # Create a container with seeded services (matching conftest.py pattern)
    container = MagicMock()  # Don't use spec to allow arbitrary attribute assignment

    # Configure service factories
    container.job_service = MagicMock(return_value=seeded_job_service)
    container.redaction_service = MagicMock(return_value=mock_redaction_service)
    container.blob_client = MagicMock(return_value=mock_blob_client)

    # Configure service and client properties (for direct access)
    container.services = MagicMock()
    container.services.job_service = MagicMock(return_value=seeded_job_service)
    container.services.redaction_service = MagicMock(return_value=mock_redaction_service)

    container.clients = MagicMock()
    container.clients.blob_client = mock_blob_client

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.container = container
        yield

    app = FastAPI(lifespan=lifespan)
    app.container = container

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(redactions.router, prefix="/api/jobs/{job_id}/redactions", tags=["redactions"])

    with patch("redactor.routes.redactions._get_blob", return_value=mock_blob_client):
        yield app


@pytest.mark.asyncio
async def test_toggle_suggestion_approval_with_service(test_app_redactions_service, mock_redaction_service):
    """Test toggling suggestion approval status."""
    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": False}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "s1"
    assert data["approved"] is False
    # Verify service was called with correct parameters
    mock_redaction_service.toggle_approval.assert_called_once_with("job-test", "s1", False)


@pytest.mark.asyncio
async def test_toggle_suggestion_approval_to_true(test_app_redactions_service, mock_redaction_service, mock_job_service, seeded_job):
    """Test toggling suggestion approval to True."""
    # First set to False
    seeded_job.suggestions[0].approved = False
    mock_job_service.get_job = AsyncMock(return_value=seeded_job)

    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": True}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["approved"] is True
    mock_redaction_service.toggle_approval.assert_called_once_with("job-test", "s1", True)


@pytest.mark.asyncio
async def test_toggle_suggestion_unknown_job(test_app_redactions_service, mock_redaction_service):
    """Test toggling approval for non-existent job."""
    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/no-such-job/redactions/s1",
            json={"approved": False}
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_toggle_suggestion_unknown_suggestion(test_app_redactions_service, mock_redaction_service):
    """Test toggling approval for non-existent suggestion."""
    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/no-such-suggestion",
            json={"approved": False}
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Suggestion not found"


@pytest.mark.asyncio
async def test_add_manual_redaction_with_service(test_app_redactions_service, mock_redaction_service):
    """Test adding a manual redaction suggestion."""
    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.post(
            "/api/jobs/job-test/redactions/manual",
            json={"page_num": 1, "rects": [{"x0": 5, "y0": 5, "x1": 50, "y1": 20}]}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Manual"
    assert data["approved"] is True
    assert data["source"] == "manual"
    # Verify service was called
    mock_redaction_service.add_manual_suggestion.assert_called_once()
    call_args = mock_redaction_service.add_manual_suggestion.call_args
    assert call_args[0][0] == "job-test"  # job_id
    assert call_args[0][1].text == "[Manual]"  # suggestion


@pytest.mark.asyncio
async def test_add_manual_redaction_persists_to_service(test_app_redactions_service, mock_redaction_service):
    """Test that manual redaction is persisted via service."""
    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.post(
            "/api/jobs/job-test/redactions/manual",
            json={"page_num": 2, "rects": [{"x0": 10, "y0": 10, "x1": 60, "y1": 25}]}
        )

    assert response.status_code == 200
    # Verify response indicates success
    data = response.json()
    assert data["source"] == "manual"
    assert data["approved"] is True
    # Verify service was called to persist
    mock_redaction_service.add_manual_suggestion.assert_called_once()


@pytest.mark.asyncio
async def test_apply_redactions_with_service(test_app_redactions_service, mock_redaction_service, mock_blob_client):
    """Test applying redactions with RedactionService."""
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"

        async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "applied"
    assert data["redaction_count"] == 1

    # Verify blob client was called
    mock_blob_client.download_original_pdf.assert_called_once_with("job-test")
    mock_blob_client.save_redacted_pdf.assert_called_once()


@pytest.mark.asyncio
async def test_apply_redactions_job_not_found(test_app_redactions_service, mock_redaction_service):
    """Test applying redactions to non-existent job."""
    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.post("/api/jobs/no-such-job/redactions/apply")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_apply_redactions_job_not_complete(test_app_redactions_service, mock_job_service, mock_redaction_service):
    """Test applying redactions when job is not complete."""
    pending_job = Job(job_id="job-pending", status=JobStatus.PROCESSING)

    # Create a new mock for this specific test
    mock_job_service_pending = AsyncMock(spec=JobService)
    mock_job_service_pending.get_job = AsyncMock(return_value=pending_job)
    test_app_redactions_service.container.services.job_service.return_value = mock_job_service_pending

    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.post("/api/jobs/job-pending/redactions/apply")

    assert response.status_code == 400
    assert response.json()["detail"] == "Job not complete"


@pytest.mark.asyncio
async def test_apply_redactions_pdf_not_found(test_app_redactions_service, mock_redaction_service, mock_blob_client):
    """Test applying redactions when PDF is not in storage."""
    mock_blob_client.download_original_pdf.side_effect = Exception("Not found")

    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        response = await client.post("/api/jobs/job-test/redactions/apply")

    assert response.status_code == 404
    assert "Original PDF not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_apply_redactions_processor_error(test_app_redactions_service, mock_redaction_service, mock_blob_client):
    """Test error handling when PDF processor fails."""
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.side_effect = Exception("PDF processing failed")

        async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")

    assert response.status_code == 500
    assert "Failed to apply redactions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_apply_redactions_no_approved_suggestions(test_app_redactions_service, mock_redaction_service, mock_blob_client):
    """Test applying redactions when no suggestions are approved."""
    # Create a job with no approved suggestions
    unapproved_job = Job(
        job_id="job-test-unapproved",
        status=JobStatus.COMPLETE,
        suggestions=[
            Suggestion(
                id="s1", job_id="job-test-unapproved", text="John Smith", category="Person",
                reasoning="PII", context="", page_num=0,
                rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)],
                approved=False, created_at=datetime.utcnow()
            )
        ]
    )

    # Setup service to return unapproved job
    test_app_redactions_service.container.services.job_service.return_value.get_job = AsyncMock(
        return_value=unapproved_job
    )

    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-empty"

        async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test-unapproved/redactions/apply")

    assert response.status_code == 200
    data = response.json()
    assert data["redaction_count"] == 0


@pytest.mark.asyncio
async def test_apply_redactions_multiple_approved_suggestions(
    test_app_redactions_service,
    mock_redaction_service,
    mock_blob_client
):
    """Test applying redactions with multiple approved suggestions."""
    # Create a job with multiple approved suggestions
    job_with_multiple = Job(
        job_id="job-test-multi",
        status=JobStatus.COMPLETE,
        suggestions=[
            Suggestion(
                id="s1", job_id="job-test-multi", text="John Smith", category="Person",
                reasoning="PII", context="", page_num=0,
                rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)],
                approved=True, created_at=datetime.utcnow()
            ),
            Suggestion(
                id="s2", job_id="job-test-multi", text="jane@example.com", category="Email",
                reasoning="PII", context="", page_num=0,
                rects=[RedactionRect(x0=110, y0=10, x1=200, y1=30)],
                approved=True, created_at=datetime.utcnow()
            )
        ]
    )

    # Setup service to return job with multiple suggestions
    test_app_redactions_service.container.services.job_service.return_value.get_job = AsyncMock(
        return_value=job_with_multiple
    )

    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"

        async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test-multi/redactions/apply")

    assert response.status_code == 200
    data = response.json()
    assert data["redaction_count"] == 2


@pytest.mark.asyncio
async def test_multiple_service_calls_in_sequence(test_app_redactions_service, mock_redaction_service):
    """Test multiple API calls in sequence with service."""
    async with AsyncClient(transport=ASGITransport(app=test_app_redactions_service), base_url="http://test") as client:
        # First: toggle approval
        response1 = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": False}
        )
        assert response1.status_code == 200

        # Second: toggle approval again
        response2 = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": True}
        )
        assert response2.status_code == 200

    # Verify service was called twice
    assert mock_redaction_service.toggle_approval.call_count == 2
