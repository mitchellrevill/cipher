"""Tests for redactions route using RedactionService dependency injection."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from redactor.models import Job, JobStatus, Suggestion, RedactionRect
from redactor.routes import jobs as jobs_module, redactions
from redactor.services.redaction_service import RedactionService
from redactor.containers.app import AppContainer
from redactor.config import get_settings


@pytest.fixture(autouse=True)
def seed_job():
    """Create a test job with suggestions for testing."""
    suggestion = Suggestion(
        id="s1", job_id="job-test", text="John Smith", category="Person",
        reasoning="PII", context="", page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)], approved=True,
        created_at=datetime.utcnow()
    )
    jobs_module._jobs["job-test"] = Job(
        job_id="job-test", status=JobStatus.COMPLETE, suggestions=[suggestion]
    )
    yield
    jobs_module._jobs.pop("job-test", None)


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
def mock_container(mock_redaction_service, mock_blob_client):
    """Create a mock AppContainer with services."""
    container = MagicMock(spec=AppContainer)
    container.redaction_service.return_value = mock_redaction_service
    container.blob_client.return_value = mock_blob_client
    return container


@pytest.fixture
def test_app(mock_container):
    """Create a test FastAPI app with mocked dependencies."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Manually set container in lifespan startup
        app.container = mock_container
        yield

    test_app = FastAPI(lifespan=lifespan)

    # Pre-set container so it's available before lifespan runs in some cases
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
async def test_toggle_suggestion_approval_with_service(test_app, mock_redaction_service):
    """Test toggling suggestion approval status."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
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
async def test_toggle_suggestion_approval_to_true(test_app, mock_redaction_service):
    """Test toggling suggestion approval to True."""
    # First set to False
    jobs_module._jobs["job-test"].suggestions[0].approved = False

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/s1",
            json={"approved": True}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["approved"] is True
    mock_redaction_service.toggle_approval.assert_called_once_with("job-test", "s1", True)


@pytest.mark.asyncio
async def test_toggle_suggestion_unknown_job(test_app, mock_redaction_service):
    """Test toggling approval for non-existent job."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/no-such-job/redactions/s1",
            json={"approved": False}
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_toggle_suggestion_unknown_suggestion(test_app, mock_redaction_service):
    """Test toggling approval for non-existent suggestion."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/job-test/redactions/no-such-suggestion",
            json={"approved": False}
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Suggestion not found"


@pytest.mark.asyncio
async def test_add_manual_redaction_with_service(test_app, mock_redaction_service):
    """Test adding a manual redaction suggestion."""
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
    # Verify service was called
    mock_redaction_service.add_manual_suggestion.assert_called_once()
    call_args = mock_redaction_service.add_manual_suggestion.call_args
    assert call_args[0][0] == "job-test"  # job_id
    assert call_args[0][1].text == "[Manual]"  # suggestion


@pytest.mark.asyncio
async def test_add_manual_redaction_persists_to_service(test_app, mock_redaction_service):
    """Test that manual redaction is persisted via service."""
    initial_count = len(jobs_module._jobs["job-test"].suggestions)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            "/api/jobs/job-test/redactions/manual",
            json={"page_num": 2, "rects": [{"x0": 10, "y0": 10, "x1": 60, "y1": 25}]}
        )

    assert response.status_code == 200
    # Verify suggestion was added to in-memory job
    assert len(jobs_module._jobs["job-test"].suggestions) == initial_count + 1
    # Verify service was called to persist
    mock_redaction_service.add_manual_suggestion.assert_called_once()


@pytest.mark.asyncio
async def test_apply_redactions_with_service(test_app, mock_redaction_service, mock_blob_client):
    """Test applying redactions with RedactionService."""
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "applied"
    assert data["redaction_count"] == 1

    # Verify blob client was called
    mock_blob_client.download_original_pdf.assert_called_once_with("job-test")
    mock_blob_client.save_redacted_pdf.assert_called_once()


@pytest.mark.asyncio
async def test_apply_redactions_job_not_found(test_app, mock_redaction_service):
    """Test applying redactions to non-existent job."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/jobs/no-such-job/redactions/apply")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_apply_redactions_job_not_complete(test_app, mock_redaction_service):
    """Test applying redactions when job is not complete."""
    jobs_module._jobs["job-pending"] = Job(job_id="job-pending", status=JobStatus.PROCESSING)
    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-pending/redactions/apply")

        assert response.status_code == 400
        assert response.json()["detail"] == "Job not complete"
    finally:
        jobs_module._jobs.pop("job-pending", None)


@pytest.mark.asyncio
async def test_apply_redactions_pdf_not_found(test_app, mock_redaction_service, mock_blob_client):
    """Test applying redactions when PDF is not in storage."""
    mock_blob_client.download_original_pdf.side_effect = Exception("Not found")

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/jobs/job-test/redactions/apply")

    assert response.status_code == 404
    assert "Original PDF not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_apply_redactions_processor_error(test_app, mock_redaction_service, mock_blob_client):
    """Test error handling when PDF processor fails."""
    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.side_effect = Exception("PDF processing failed")

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")

    assert response.status_code == 500
    assert "Failed to apply redactions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_apply_redactions_no_approved_suggestions(test_app, mock_redaction_service, mock_blob_client):
    """Test applying redactions when no suggestions are approved."""
    # Unapprove all suggestions
    for s in jobs_module._jobs["job-test"].suggestions:
        s.approved = False

    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-empty"

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")

    assert response.status_code == 200
    data = response.json()
    assert data["redaction_count"] == 0


@pytest.mark.asyncio
async def test_apply_redactions_multiple_approved_suggestions(
    test_app,
    mock_redaction_service,
    mock_blob_client
):
    """Test applying redactions with multiple approved suggestions."""
    # Add another approved suggestion
    suggestion2 = Suggestion(
        id="s2", job_id="job-test", text="jane@example.com", category="Email",
        reasoning="PII", context="", page_num=0,
        rects=[RedactionRect(x0=110, y0=10, x1=200, y1=30)], approved=True,
        created_at=datetime.utcnow()
    )
    jobs_module._jobs["job-test"].suggestions.append(suggestion2)

    with patch("redactor.routes.redactions.PDFProcessor") as MockPDF:
        MockPDF.return_value.apply_redactions.return_value = b"%PDF-redacted"

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/jobs/job-test/redactions/apply")

    assert response.status_code == 200
    data = response.json()
    assert data["redaction_count"] == 2


@pytest.mark.asyncio
async def test_service_dependency_injection():
    """Test that RedactionService is properly injected via container."""
    from redactor.containers.app import AppContainer

    container = AppContainer()
    container.config.from_dict({
        'cosmos_endpoint': 'http://localhost:8081',
        'azure_storage_account_url': 'https://example.blob.core.windows.net',
        'azure_openai_endpoint': 'https://example.openai.azure.com/',
        'azure_openai_api_version': '2024-02-15-preview',
    })

    # Get redaction service from container
    service = container.redaction_service()

    # Verify it's a RedactionService instance
    assert isinstance(service, RedactionService)


@pytest.mark.asyncio
async def test_multiple_service_calls_in_sequence(test_app, mock_redaction_service):
    """Test multiple API calls in sequence with service."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
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
