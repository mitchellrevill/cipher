"""Tests for agent route with AgentService dependency injection."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock
from datetime import datetime
from redactor.models import Job, JobStatus


# Note: All service and container mocks are now defined in conftest.py
# Use the test_app_agent_only fixture for agent-specific tests


@pytest.mark.asyncio
async def test_chat_creates_session_when_none_provided(mock_agent_service, test_app):
    """Verify POST /chat creates a new session when session_id is not provided."""
    job = Job(job_id="job-123", filename="test.pdf", status=JobStatus.COMPLETE)
    mock_agent_service.job_service.get_job.return_value = job

    mock_agent_service.create_session.return_value = "sess-abc"

    mock_agent_service.run_turn.return_value = {
        "text": "I found 3 redactions.",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-123",
            "message": "What has been redacted?",
            "session_id": None,
        })

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "sess-abc"
    assert data["response"] == "I found 3 redactions."
    mock_agent_service.create_session.assert_called_once_with("job-123")


@pytest.mark.asyncio
async def test_chat_uses_existing_session_when_provided(mock_agent_service, test_app):
    """Verify POST /chat uses existing session when session_id is provided."""
    job = Job(job_id="job-123", filename="test.pdf", status=JobStatus.COMPLETE)
    mock_agent_service.job_service.get_job.return_value = job

    existing_session = {"session": MagicMock(session_id="sess-existing"), "job_id": "job-123"}
    mock_agent_service.get_session.return_value = existing_session

    mock_agent_service.run_turn.return_value = {
        "text": "All PII has been removed.",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-123",
            "message": "Has all PII been removed?",
            "session_id": "sess-existing",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "sess-existing"
    assert data["response"] == "All PII has been removed."
    mock_agent_service.get_session.assert_called_once_with("sess-existing")
    mock_agent_service.create_session.assert_not_called()


@pytest.mark.asyncio
async def test_chat_calls_run_turn_with_session_context(mock_agent_service, test_app):
    """Verify POST /chat calls run_turn with the new session-centric contract."""
    job = Job(job_id="job-123", filename="test.pdf", status=JobStatus.COMPLETE)
    mock_agent_service.job_service.get_job.return_value = job

    mock_agent_service.create_session.return_value = "sess-abc"

    mock_agent_service.run_turn.return_value = {
        "text": "Response text",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-123",
            "message": "What was redacted?",
            "session_id": None,
        })

    assert response.status_code == 200
    mock_agent_service.run_turn.assert_called_once_with(
        session_id="sess-abc",
        message="What was redacted?",
    )


@pytest.mark.asyncio
async def test_chat_calls_run_turn_with_workspace_id(mock_agent_service, test_app):
    """Verify POST /chat forwards workspace_id when provided."""
    job = Job(job_id="job-123", filename="test.pdf", status=JobStatus.COMPLETE)
    mock_agent_service.job_service.get_job.return_value = job
    mock_agent_service.create_session.return_value = "sess-abc"
    mock_agent_service.run_turn.return_value = {"text": "Response"}

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-123",
            "message": "What are suggestions?",
            "workspace_id": "ws-1",
            "session_id": None,
        })

    assert response.status_code == 200
    mock_agent_service.run_turn.assert_called_once_with(
        session_id="sess-abc",
        workspace_id="ws-1",
        message="What are suggestions?",
    )


@pytest.mark.asyncio
async def test_chat_returns_404_when_job_not_found(mock_agent_service, test_app):
    """Verify POST /chat returns 404 when job doesn't exist."""
    mock_agent_service.job_service.get_job.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "nonexistent-job",
            "message": "hello",
            "session_id": None,
        })

    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_returns_404_when_session_not_found(mock_agent_service, test_app):
    """Verify POST /chat returns 404 when session doesn't exist."""
    job = Job(job_id="job-123", filename="test.pdf", status=JobStatus.COMPLETE)
    mock_agent_service.job_service.get_job.return_value = job
    mock_agent_service.get_session.return_value = None

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-123",
            "message": "hello",
            "session_id": "nonexistent-sess",
        })

    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_response_format(mock_agent_service, test_app):
    """Verify POST /chat returns correct response format."""
    job = Job(job_id="job-123", filename="test.pdf", status=JobStatus.COMPLETE)
    mock_agent_service.job_service.get_job.return_value = job

    mock_agent_service.create_session.return_value = "sess-abc"

    mock_agent_service.run_turn.return_value = {
        "text": "Assistant response",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-123",
            "message": "Test message",
            "session_id": None,
        })

    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "response" in data
    assert data["session_id"] == "sess-abc"
    assert data["response"] == "Assistant response"


@pytest.mark.asyncio
async def test_chat_uses_injected_agent_service(mock_agent_service, test_app):
    """Verify POST /chat uses AgentService from dependency injection."""
    job = Job(job_id="job-123", filename="test.pdf", status=JobStatus.COMPLETE)
    mock_agent_service.job_service.get_job.return_value = job

    mock_agent_service.create_session.return_value = "sess-abc"

    mock_agent_service.run_turn.return_value = {
        "text": "Response",
    }

    # Test that the container.agent_service() is called
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-123",
            "message": "Test",
            "session_id": None,
        })

    assert response.status_code == 200
    # Verify container was used to get the service
    test_app.container.agent_service.assert_called()
