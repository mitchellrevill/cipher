"""
Shared test fixtures and configuration for the redactor test suite.

This module consolidates common test fixtures and setup across all test files,
ensuring consistency with the service-based architecture and dependency injection patterns.
"""
import pytest
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from redactor.containers.app import AppContainer
from redactor.config import get_settings
from redactor.models import Job, JobStatus, Suggestion, RedactionRect
from redactor.services.agent_service import AgentService
from redactor.services.blob_service import BlobService
from redactor.services.job_service import JobService
from redactor.services.redaction_service import RedactionService
from redactor.services.workspace_service import WorkspaceService


# ============================================================================
# Service Fixtures
# ============================================================================

@pytest.fixture
def mock_cosmos_client():
    """Create a mock Cosmos DB client for service tests."""
    return MagicMock()


@pytest.fixture
def mock_blob_client():
    """Create a mock Azure Blob Storage client for service and route tests."""
    client = MagicMock()
    # Configure async methods for blob operations
    client.upload_pdf = AsyncMock(return_value="https://blob.url/pdf")
    client.download_original_pdf = AsyncMock(return_value=b"%PDF")
    client.download_redacted_pdf = AsyncMock(return_value=b"%PDF-redacted")
    client.save_redacted_pdf = AsyncMock()
    client.save_suggestions = AsyncMock()
    client.delete_pdfs = AsyncMock()
    return client


@pytest.fixture
def mock_oai_client():
    """Create a mock Azure OpenAI client for service tests."""
    return AsyncMock()


@pytest.fixture
def mock_job_service():
    """Create a mock JobService for integration tests."""
    service = MagicMock(spec=JobService)
    service.create_job = AsyncMock()
    service.get_job = AsyncMock()
    service.update_status = AsyncMock()
    service.update_suggestions = AsyncMock()
    service.list_jobs = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_redaction_service():
    """Create a mock RedactionService for integration tests."""
    service = AsyncMock(spec=RedactionService)
    service.get_suggestions = AsyncMock(return_value=[])
    service.save_suggestions = AsyncMock(return_value=[])
    service.toggle_approval = AsyncMock(return_value=None)
    service.bulk_update_approvals = AsyncMock(return_value=0)
    service.add_manual_suggestion = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_agent_service(mock_job_service):
    """Create a mock AgentService for integration tests."""
    service = MagicMock(spec=AgentService)
    service.create_session = AsyncMock()
    service.get_session = AsyncMock()
    service.save_message = AsyncMock()
    service.run_turn = AsyncMock()
    service.job_service = mock_job_service
    return service


@pytest.fixture
def mock_workspace_service():
    """Create a mock WorkspaceService for integration tests."""
    service = MagicMock(spec=WorkspaceService)
    service.create_workspace = AsyncMock()
    service.get_workspace = AsyncMock()
    service.get_workspace_state = AsyncMock()
    service.list_workspaces = AsyncMock(return_value=[])
    service.add_document = AsyncMock()
    service.remove_document = AsyncMock()
    service.create_rule = AsyncMock()
    service.exclude_document = AsyncMock()
    service.remove_exclusion = AsyncMock()
    return service


# ============================================================================
# Container Fixture
# ============================================================================

@pytest.fixture
def mock_container(mock_job_service, mock_redaction_service, mock_agent_service, mock_workspace_service, mock_blob_client):
    """
    Create a mock AppContainer with all services properly configured.

    This fixture provides dependency injection for route tests, allowing
    tests to verify route behavior using mocked services.
    """
    container = MagicMock()  # Don't use spec to allow arbitrary attribute assignment

    job_factory = MagicMock(return_value=mock_job_service)
    redaction_factory = MagicMock(return_value=mock_redaction_service)
    agent_factory = MagicMock(return_value=mock_agent_service)
    workspace_factory = MagicMock(return_value=mock_workspace_service)

    # Configure service factory methods
    container.job_service = job_factory
    container.redaction_service = redaction_factory
    container.agent_service = agent_factory
    container.workspace_service = workspace_factory
    container.workspace_service.return_value = mock_workspace_service

    # Configure blob client
    container.blob_client.return_value = mock_blob_client

    # Configure service properties (for direct access)
    container.services = MagicMock()
    container.services.job_service = job_factory
    container.services.redaction_service = redaction_factory
    container.services.agent_service = agent_factory
    container.services.workspace_service = workspace_factory

    # Configure clients
    container.clients = MagicMock()
    container.clients.blob_client = mock_blob_client

    return container


# ============================================================================
# Test App Fixtures
# ============================================================================

@pytest.fixture
def test_app(mock_container):
    """
    Create a test FastAPI application with all routes and mocked dependencies.

    This is the primary fixture for route testing. It includes all routers
    and uses the mock_container for dependency injection.
    """
    from redactor.routes import jobs, redactions, agent, workspaces
    from fastapi.middleware.cors import CORSMiddleware

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Inject mock container during startup
        app.container = mock_container
        yield

    app = FastAPI(lifespan=lifespan)
    app.container = mock_container

    # Configure CORS middleware
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all route routers
    app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    app.include_router(redactions.router, prefix="/api/jobs/{job_id}/redactions", tags=["redactions"])
    app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
    app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])

    return app


@pytest.fixture
def test_app_jobs_only(mock_container):
    """
    Create a test FastAPI application with only the jobs router.

    Use this fixture when testing jobs route in isolation.
    """
    from redactor.routes import jobs
    from fastapi.middleware.cors import CORSMiddleware

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.container = mock_container
        yield

    app = FastAPI(lifespan=lifespan)
    app.container = mock_container

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    return app


@pytest.fixture
def test_app_redactions_only(mock_container):
    """
    Create a test FastAPI application with only the redactions router.

    Use this fixture when testing redactions route in isolation.
    """
    from redactor.routes import redactions
    from fastapi.middleware.cors import CORSMiddleware

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.container = mock_container
        yield

    app = FastAPI(lifespan=lifespan)
    app.container = mock_container

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(redactions.router, prefix="/api/jobs/{job_id}/redactions", tags=["redactions"])
    return app


@pytest.fixture
def test_app_agent_only(mock_container):
    """
    Create a test FastAPI application with only the agent router.

    Use this fixture when testing agent route in isolation.
    """
    from redactor.routes import agent
    from fastapi.middleware.cors import CORSMiddleware

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.container = mock_container
        yield

    app = FastAPI(lifespan=lifespan)
    app.container = mock_container

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
    return app


# ============================================================================
# HTTP Client Fixture
# ============================================================================

@pytest.fixture
async def async_client(test_app):
    """Create an AsyncClient for making requests to the test app."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client


# ============================================================================
# Model Data Fixtures
# ============================================================================

@pytest.fixture
def sample_job():
    """Create a sample Job object for testing."""
    return Job(
        job_id="job-test-123",
        filename="test.pdf",
        status=JobStatus.PENDING,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_suggestion():
    """Create a sample Suggestion object for testing."""
    return Suggestion(
        id="sugg-1",
        job_id="job-test-123",
        text="John Smith",
        category="Person",
        reasoning="PII - Full name detected",
        context="Found in paragraph 2",
        page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=100, y1=30)],
        approved=False,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def completed_job_with_suggestions(sample_job, sample_suggestion):
    """Create a completed job with suggestions for testing."""
    job = Job(
        job_id="job-complete-123",
        filename="complete.pdf",
        status=JobStatus.COMPLETE,
        created_at=datetime.utcnow(),
        suggestions=[sample_suggestion]
    )
    return job


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (deselect with '-m \"not asyncio\"')"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
