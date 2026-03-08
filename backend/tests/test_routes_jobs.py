import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from redactor.main import app

@pytest.mark.asyncio
async def test_upload_returns_job_id():
    with patch("redactor.routes.jobs.BlobStorageClient") as MockBlob, \
         patch("redactor.routes.jobs.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        MockBlob.return_value.upload_pdf = AsyncMock(return_value="jobs/123/original.pdf")
        MockBlob.return_value.save_suggestions = AsyncMock()
        mock_pipeline.return_value = []
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/jobs",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
                data={"instructions": "remove names"}
            )
    assert response.status_code == 202
    assert "job_id" in response.json()

@pytest.mark.asyncio
async def test_get_job_returns_404_for_unknown():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_job_returns_job_for_existing():
    from redactor.routes.jobs import _jobs
    from redactor.models import Job, JobStatus
    test_job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    _jobs[test_job_id] = Job(job_id=test_job_id, status=JobStatus.PENDING)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/jobs/{test_job_id}")
        assert response.status_code == 200
        assert response.json()["job_id"] == test_job_id
    finally:
        _jobs.pop(test_job_id, None)
