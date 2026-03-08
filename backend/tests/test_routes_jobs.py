import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from redactor.main import app

@pytest.mark.asyncio
async def test_upload_returns_job_id():
    with patch("redactor.routes.jobs.BlobStorageClient") as MockBlob, \
         patch("redactor.routes.jobs.run_pipeline") as mock_pipeline, \
         patch("redactor.routes.jobs.asyncio.create_task"):
        MockBlob.return_value.upload_pdf = AsyncMock(return_value="jobs/123/original.pdf")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/jobs",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
                data={"instructions": "remove names"}
            )
    assert response.status_code == 202
    assert "job_id" in response.json()

@pytest.mark.asyncio
async def test_get_job_status_returns_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/jobs/nonexistent-job")
    assert response.status_code in (200, 404)
