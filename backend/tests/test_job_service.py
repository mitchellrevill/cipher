"""Tests for JobService."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from redactor.services.job_service import JobService
from redactor.models import Job, JobStatus


@pytest.fixture
def mock_cosmos_client():
    """Create a mock Cosmos DB client."""
    return MagicMock()


@pytest.fixture
def job_service(mock_cosmos_client):
    """Create a JobService instance with mocked Cosmos client."""
    return JobService(cosmos_client=mock_cosmos_client)


@pytest.mark.asyncio
async def test_create_job(job_service, mock_cosmos_client):
    """Verify JobService.create_job creates and persists a job."""
    now = datetime.utcnow()
    mock_cosmos_client.create_item.return_value = {
        "id": "job-123",
        "job_id": "job-123",
        "filename": "test.pdf",
        "status": "pending",
        "created_at": now.isoformat(),
        "page_count": 0,
        "error": None,
        "completed_at": None,
        "user_id": None,
        "suggestions_count": 0
    }

    job = await job_service.create_job(job_id="job-123", filename="test.pdf")

    assert job.job_id == "job-123"
    assert job.filename == "test.pdf"
    assert job.status == JobStatus.PENDING
    mock_cosmos_client.create_item.assert_called_once()


@pytest.mark.asyncio
async def test_get_job(job_service, mock_cosmos_client):
    """Verify JobService.get_job retrieves a job."""
    now = datetime.utcnow()
    mock_cosmos_client.read_item.return_value = {
        "id": "job-123",
        "job_id": "job-123",
        "filename": "test.pdf",
        "status": "pending",
        "created_at": now.isoformat(),
        "page_count": 0,
        "error": None,
        "completed_at": None,
        "user_id": None,
        "suggestions_count": 0
    }

    job = await job_service.get_job(job_id="job-123")

    assert job is not None
    assert job.job_id == "job-123"
    mock_cosmos_client.read_item.assert_called_once()


@pytest.mark.asyncio
async def test_get_job_not_found(job_service, mock_cosmos_client):
    """Verify JobService.get_job returns None when job not found."""
    mock_cosmos_client.read_item.side_effect = Exception("Not found")

    job = await job_service.get_job(job_id="nonexistent")

    assert job is None


@pytest.mark.asyncio
async def test_update_status(job_service, mock_cosmos_client):
    """Verify JobService.update_status updates job status."""
    now = datetime.utcnow()
    mock_cosmos_client.update_item.return_value = {
        "id": "job-123",
        "job_id": "job-123",
        "status": "complete",
        "completed_at": now.isoformat()
    }

    await job_service.update_status(job_id="job-123", status=JobStatus.COMPLETE)

    mock_cosmos_client.update_item.assert_called_once()


@pytest.mark.asyncio
async def test_update_suggestions(job_service, mock_cosmos_client):
    """Verify JobService.update_suggestions updates suggestion count."""
    await job_service.update_suggestions(job_id="job-123", suggestions_count=5)

    mock_cosmos_client.update_item.assert_called_once()


@pytest.mark.asyncio
async def test_list_jobs(job_service, mock_cosmos_client):
    """Verify JobService.list_jobs returns list of jobs."""
    jobs = await job_service.list_jobs()

    assert isinstance(jobs, list)
