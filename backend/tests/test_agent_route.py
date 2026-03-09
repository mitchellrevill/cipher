"""Tests for agent route - legacy tests updated for service injection."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from fastapi import FastAPI
from redactor.models import Job, JobStatus
from redactor.services.agent_service import AgentService
from redactor.services.job_service import JobService
from redactor.containers.app import AppContainer


@pytest.fixture
def mock_agent_service():
    """Create a mock AgentService."""
    service = MagicMock(spec=AgentService)
    service.create_session = AsyncMock()
    service.get_session = AsyncMock()
    service.save_message = AsyncMock()
    service.run_turn = AsyncMock()
    service.job_service = MagicMock(spec=JobService)
    service.job_service.get_job = AsyncMock()
    return service


@pytest.fixture
def mock_container(mock_agent_service):
    """Create a mock AppContainer with services."""
    container = MagicMock(spec=AppContainer)
    container.agent_service.return_value = mock_agent_service
    return container


@pytest.fixture
def test_app(mock_container):
    """Create a test FastAPI app with mocked dependencies."""
    from redactor.routes import agent
    from redactor.config import get_settings

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
    test_app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
    return test_app


@pytest.mark.asyncio
async def test_chat_returns_response(mock_agent_service, test_app):
    """Verify POST /chat returns response with correct format."""
    job = Job(job_id="job-agent", filename="test.pdf", status=JobStatus.COMPLETE)
    mock_agent_service.job_service.get_job.return_value = job

    new_session = {"id": "sess-abc", "job_id": "job-agent", "messages": []}
    mock_agent_service.create_session.return_value = new_session

    mock_agent_service.run_turn.return_value = {
        "text": "I found 3 redactions.",
        "response_id": "resp-abc",
        "tool_calls": []
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-agent",
            "message": "What has been redacted?",
            "session_id": None,
            "previous_response_id": None
        })

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "response_id" in data
    assert "session_id" in data


@pytest.mark.asyncio
async def test_chat_returns_404_for_unknown_job(mock_agent_service, test_app):
    """Verify POST /chat returns 404 when job not found."""
    mock_agent_service.job_service.get_job.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "nonexistent",
            "message": "hello",
            "session_id": None,
            "previous_response_id": None
        })

    assert response.status_code == 404
