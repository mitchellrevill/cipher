import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redactor.models import Job, JobStatus
from redactor.services.job_service import JobService
from redactor.containers.app import AppContainer
from redactor.config import get_settings
from redactor.routes import jobs


@pytest.fixture
def mock_job_service():
    """Create a mock JobService."""
    service = MagicMock(spec=JobService)
    service.create_job = AsyncMock()
    service.get_job = AsyncMock()
    return service


@pytest.fixture
def mock_blob_client():
    """Create a mock BlobStorageClient."""
    client = MagicMock()
    client.upload_pdf = AsyncMock()
    client.download_redacted_pdf = AsyncMock()
    client.save_suggestions = AsyncMock()
    return client


@pytest.fixture
def mock_container(mock_job_service, mock_blob_client):
    """Create a mock AppContainer with services."""
    container = MagicMock(spec=AppContainer)
    container.job_service.return_value = mock_job_service
    container.blob_client.return_value = mock_blob_client
    return container


@pytest.fixture
def test_app_legacy(mock_container):
    """Create a test FastAPI app with mocked dependencies for legacy tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.container = mock_container
        yield

    test_app = FastAPI(lifespan=lifespan)
    test_app.container = mock_container

    settings = get_settings()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    return test_app


@pytest.mark.asyncio
async def test_upload_returns_job_id(mock_job_service, mock_blob_client, test_app_legacy):
    """Verify POST /jobs returns job ID."""
    now = datetime.now()
    created_job = Job(
        job_id="test-job-123",
        filename="test.pdf",
        status=JobStatus.PENDING,
        created_at=now
    )
    mock_job_service.create_job.return_value = created_job

    with patch("redactor.routes.jobs._run_job", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=test_app_legacy), base_url="http://test") as client:
            response = await client.post(
                "/api/jobs",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
                data={"instructions": "remove names"}
            )
    assert response.status_code == 202
    assert "job_id" in response.json()


@pytest.mark.asyncio
async def test_get_job_returns_404_for_unknown(mock_job_service, mock_blob_client, test_app_legacy):
    """Verify GET /jobs/{id} returns 404 when not found."""
    mock_job_service.get_job.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app_legacy), base_url="http://test") as client:
        response = await client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_returns_job_for_existing(mock_job_service, mock_blob_client, test_app_legacy):
    """Verify GET /jobs/{id} returns job when found."""
    test_job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    now = datetime.now()
    job = Job(job_id=test_job_id, status=JobStatus.PENDING, created_at=now)
    mock_job_service.get_job.return_value = job

    async with AsyncClient(transport=ASGITransport(app=test_app_legacy), base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{test_job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == test_job_id
