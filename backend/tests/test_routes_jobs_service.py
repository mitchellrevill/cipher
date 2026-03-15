"""Tests for jobs route with JobService dependency injection."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from datetime import datetime
from redactor.models import Job, JobStatus


# Note: All service and container mocks are now defined in conftest.py
# Use the test_app fixture which includes the jobs router and all mocked services


@pytest.mark.asyncio
async def test_upload_document_creates_job_via_service(mock_job_service, mock_blob_client, test_app):
    """Verify POST /jobs creates job via JobService."""
    now = datetime.now()
    created_job = Job(
        job_id="job-123",
        filename="test.pdf",
        status=JobStatus.PENDING,
        created_at=now,
        blob_path="jobs/job-123/original.pdf",
        output_blob_path="jobs/job-123/redacted.pdf",
    )
    mock_job_service.create_job.return_value = created_job

    with patch("redactor.routes.jobs._run_job", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/jobs",
                files={"file": ("test.pdf", b"PDF content")},
                data={"instructions": "Redact all PII"}
            )

    assert response.status_code == 202
    assert "job_id" in response.json()
    mock_job_service.create_job.assert_called_once()


@pytest.mark.asyncio
async def test_upload_document_calls_blob_upload(mock_job_service, mock_blob_client, test_app):
    """Verify POST /jobs uploads PDF to blob storage."""
    now = datetime.now()
    created_job = Job(
        job_id="job-456",
        filename="document.pdf",
        status=JobStatus.PENDING,
        created_at=now,
        blob_path="jobs/job-456/original.pdf",
        output_blob_path="jobs/job-456/redacted.pdf",
    )
    mock_job_service.create_job.return_value = created_job

    with patch("redactor.routes.jobs._run_job", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/jobs",
                files={"file": ("document.pdf", b"PDF content here")},
            )

    assert response.status_code == 202
    mock_blob_client.upload_pdf.assert_called_once()


@pytest.mark.asyncio
async def test_get_job_returns_job_from_service(mock_job_service, mock_blob_client, test_app):
    """Verify GET /jobs/{id} calls JobService and returns job."""
    now = datetime.now()
    job = Job(
        job_id="job-789",
        filename="test.pdf",
        status=JobStatus.COMPLETE,
        created_at=now,
        blob_path="jobs/job-789/original.pdf",
        output_blob_path="jobs/job-789/redacted.pdf",
    )
    mock_job_service.get_job.return_value = job

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/jobs/job-789")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-789"
    assert data["status"] == "complete"
    mock_job_service.get_job.assert_called_once_with("job-789")


@pytest.mark.asyncio
async def test_get_job_returns_404_when_not_found(mock_job_service, mock_blob_client, test_app):
    """Verify GET /jobs/{id} returns 404 when job not found."""
    mock_job_service.get_job.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/jobs/nonexistent-job")

    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_stream_endpoint_polls_service(mock_job_service, mock_blob_client, test_app):
    """Verify GET /jobs/{id}/stream calls JobService repeatedly."""
    now = datetime.now()
    job_id = "123e4567-e89b-12d3-a456-426614174000"
    job = Job(
        job_id=job_id,
        status=JobStatus.COMPLETE,
        created_at=now,
        blob_path=f"jobs/{job_id}/original.pdf",
        output_blob_path=f"jobs/{job_id}/redacted.pdf",
    )
    mock_job_service.get_job.return_value = job

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{job_id}/stream")
        await response.aread()

    assert response.status_code == 200
    # Verify service was called at least once
    mock_job_service.get_job.assert_called()


@pytest.mark.asyncio
@pytest.mark.skip(reason="SSE event loop handling in test environment requires separate integration test setup")
async def test_stream_endpoint_returns_404_for_missing_job(mock_job_service, mock_blob_client, test_app):
    """Verify stream endpoint sends not found when job doesn't exist."""
    mock_job_service.get_job.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/jobs/nonexistent/stream")

    assert response.status_code == 200
    # SSE responses are text/event-stream, check content
    assert "error" in response.text


@pytest.mark.asyncio
async def test_download_redacted_pdf(mock_blob_client, test_app):
    """Verify GET /jobs/{id}/download downloads redacted PDF."""
    pdf_content = b"PDF redacted content"
    mock_blob_client.download_redacted_pdf.return_value = pdf_content

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/jobs/job-123/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    mock_blob_client.download_redacted_pdf.assert_called_once_with("job-123")


@pytest.mark.asyncio
async def test_download_returns_404_when_pdf_not_found(mock_blob_client, test_app):
    """Verify download returns 404 when PDF doesn't exist."""
    mock_blob_client.download_redacted_pdf.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/jobs/job-123/download")

    assert response.status_code == 404
    assert "Redacted PDF not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_job_updates_service_status(mock_job_service, mock_blob_client):
    """Verify _run_job calls service update methods."""
    from redactor.routes.jobs import _run_job
    from redactor.models import Suggestion

    pdf_bytes = b"PDF content"
    job_id = "job-xyz"
    suggestions = [
        Suggestion(
            id="s1",
            job_id=job_id,
            text="PII text",
            category="PII",
            reasoning="Contains SSN",
            context="context",
            page_num=1,
            rects=[],
            approved=False,
            created_at=datetime.now()
        )
    ]

    with patch("redactor.routes.jobs.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = suggestions
        await _run_job(job_id, pdf_bytes, "instructions", mock_blob_client, mock_job_service)

    # Verify service was called to update status and save suggestions in blob
    mock_job_service.update_status.assert_any_call(job_id, JobStatus.PROCESSING)
    mock_blob_client.save_suggestions.assert_called_once_with(job_id, suggestions)
    mock_job_service.update_status.assert_any_call(job_id, JobStatus.COMPLETE)


@pytest.mark.asyncio
async def test_run_job_handles_pipeline_error(mock_job_service, mock_blob_client):
    """Verify _run_job marks job as failed on pipeline error."""
    from redactor.routes.jobs import _run_job

    job_id = "job-error"

    with patch("redactor.routes.jobs.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.side_effect = Exception("Pipeline failed")
        await _run_job(job_id, b"PDF", "instructions", mock_blob_client, mock_job_service)

    # Verify job marked as failed with error message
    calls = mock_job_service.update_status.call_args_list
    assert any(
        call[0][1] == JobStatus.FAILED and "Pipeline failed" in call[0][2]
        for call in calls
    )


@pytest.mark.asyncio
async def test_run_job_does_not_call_update_suggestions(mock_job_service, mock_blob_client):
    from redactor.routes.jobs import _run_job
    from redactor.models import Suggestion

    suggestions = [
        Suggestion(
            id="s1",
            job_id="job-xyz",
            text="PII text",
            category="PII",
            reasoning="Contains SSN",
            context="context",
            page_num=1,
            rects=[],
            approved=False,
            created_at=datetime.now(),
        )
    ]

    with patch("redactor.routes.jobs.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = suggestions
        await _run_job("job-xyz", b"PDF", "instructions", mock_blob_client, mock_job_service)

    assert not hasattr(mock_job_service, "update_suggestions") or mock_job_service.update_suggestions.await_count == 0


@pytest.mark.asyncio
async def test_delete_suggestion_returns_204(test_app, mock_job_service, mock_redaction_service, sample_suggestion):
    mock_job_service.get_job.return_value = Job(
        job_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        status=JobStatus.COMPLETE,
        suggestions=[sample_suggestion],
    )

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.delete("/api/jobs/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/suggestions/sugg-1")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_suggestion_returns_400_for_invalid_uuid(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.delete("/api/jobs/not-a-uuid/suggestions/sugg-1")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid job ID"


@pytest.mark.asyncio
async def test_delete_suggestion_returns_404_for_unknown_job(test_app, mock_job_service):
    mock_job_service.get_job.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.delete("/api/jobs/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/suggestions/sugg-1")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_delete_suggestion_returns_404_for_unknown_suggestion(test_app, mock_job_service):
    mock_job_service.get_job.return_value = Job(
        job_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        status=JobStatus.COMPLETE,
        suggestions=[],
    )

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.delete("/api/jobs/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/suggestions/no-such")

    assert response.status_code == 404
    assert response.json()["detail"] == "Suggestion not found"
