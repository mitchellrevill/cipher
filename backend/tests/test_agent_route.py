"""Tests for agent route - service-based architecture."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from redactor.models import Job, JobStatus


# Note: All service and container mocks are now defined in conftest.py
# Use the test_app_agent_only fixture for agent-specific tests, or test_app for full stack


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
