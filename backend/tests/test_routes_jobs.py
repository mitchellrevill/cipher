"""Tests for jobs routes."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from datetime import datetime
from app.models import Job, JobStatus


# Note: Service and container mocks are now defined in conftest.py
# The test_app fixture automatically includes the jobs router
@pytest.mark.asyncio
async def test_upload_returns_job_id(mock_job_service, mock_blob_client, test_app):
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
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/jobs",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
                data={"instructions": "remove names"}
            )
    assert response.status_code == 202
    assert "job_id" in response.json()


@pytest.mark.asyncio
async def test_get_job_returns_404_for_unknown(mock_job_service, mock_blob_client, test_app):
    """Verify GET /jobs/{id} returns 404 when not found."""
    mock_job_service.get_job.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_returns_job_for_existing(mock_job_service, mock_blob_client, test_app):
    """Verify GET /jobs/{id} returns job when found."""
    test_job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    now = datetime.now()
    job = Job(job_id=test_job_id, status=JobStatus.PENDING, created_at=now, user_id="test-user-123")
    mock_job_service.get_job.return_value = job

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{test_job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == test_job_id
