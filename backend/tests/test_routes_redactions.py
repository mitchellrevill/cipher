import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from redactor.models import Job, JobStatus, Suggestion, RedactionRect
from redactor.routes import redactions
from redactor.services.redaction_service import RedactionService
from redactor.services.job_service import JobService
from redactor.containers.app import AppContainer
from redactor.config import get_settings


@pytest.fixture
def seeded_job():
    """Create a test job with suggestions for testing."""
    suggestion = Suggestion(
        id="s1", job_id="job-test", text="John Smith", category="Person",
        reasoning="PII", context="", page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)], approved=True, created_at=datetime.utcnow()
    )
    return Job(
        job_id="job-test", status=JobStatus.COMPLETE, suggestions=[suggestion]
    )


@pytest.fixture
def mock_job_service(seeded_job):
    """Create a mock JobService with a test job."""
    service = AsyncMock(spec=JobService)

    async def get_job_side_effect(job_id: str):
        """Return seeded job for known job_id, None otherwise."""
        if job_id == "job-test":
            return seeded_job
        return None

    service.get_job = AsyncMock(side_effect=get_job_side_effect)
    return service


@pytest.fixture
def mock_redaction_service():
    """Create a mock RedactionService."""
    service = AsyncMock(spec=RedactionService)
    service.get_suggestions = AsyncMock(return_value=[])
    service.toggle_approval = AsyncMock(return_value=None)
    service.add_manual_suggestion = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_blob_client():
    """Create a mock BlobStorageClient."""
    client = MagicMock()
    client.download_original_pdf = AsyncMock(return_value=b"%PDF")
    client.save_redacted_pdf = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_container(mock_job_service, mock_redaction_service, mock_blob_client):
    """Create a mock AppContainer with services."""
    container = MagicMock(spec=AppContainer)
    container.job_service.return_value = mock_job_service
    container.redaction_service.return_value = mock_redaction_service
    container.blob_client.return_value = mock_blob_client
    return container


@pytest.fixture
def test_app(mock_container):
    """Create a test FastAPI app with mocked dependencies."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.container = mock_container
        yield

    test_app = FastAPI(lifespan=lifespan)
    test_app.container = mock_container

    settings = get_settings()
    from fastapi.middleware.cors import CORSMiddleware
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(redactions.router, prefix="/api/jobs/{job_id}/redactions", tags=["redactions"])
    return test_app

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
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_apply_redactions_response_body(test_app, mock_blob_client):
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
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
async def test_apply_redactions_job_not_complete(test_app, mock_job_service, mock_redaction_service):
    pending_job = Job(job_id="job-pending", status=JobStatus.PROCESSING)
    mock_job_service.get_job = AsyncMock(return_value=pending_job)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/jobs/job-pending/redactions/apply")
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_apply_redactions_with_none_approved(test_app, mock_blob_client, seeded_job):
    # Toggle s1 to unapproved first
    seeded_job.suggestions[0].approved = False
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-empty"
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")
    assert response.status_code == 200
    assert response.json()["redaction_count"] == 0
