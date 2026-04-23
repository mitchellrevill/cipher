"""Tests for agent route - service-based architecture."""
import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from app.models import Job, JobStatus


# Note: All service and container mocks are now defined in conftest.py
# Use the test_app_agent_only fixture for agent-specific tests, or test_app for full stack


@pytest.mark.asyncio
async def test_chat_returns_response(mock_agent_service, test_app):
    """Verify POST /chat returns response with correct format."""
    job = Job(job_id="job-agent", filename="test.pdf", status=JobStatus.COMPLETE, user_id="test-user-123")
    mock_agent_service.job_service.get_job.return_value = job

    mock_agent_service.create_session.return_value = "sess-abc"

    mock_agent_service.run_turn.return_value = {
        "text": "I found 3 redactions.",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "job-agent",
            "message": "What has been redacted?",
            "session_id": None,
        })

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
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
        })

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_stream_returns_sse_events(mock_agent_service, test_app):
    job = Job(job_id="job-agent", filename="test.pdf", status=JobStatus.COMPLETE, user_id="test-user-123")
    mock_agent_service.job_service.get_job.return_value = job
    mock_agent_service.create_session.return_value = "sess-stream"

    async def fake_stream(**kwargs):
        yield {"type": "session", "session_id": "sess-stream"}
        yield {"type": "text_delta", "delta": "Hello"}
        yield {"type": "tool_start", "tool_name": "search_document"}
        yield {"type": "tool_result", "tool_name": "search_document", "summary": "Found 2 results"}
        yield {"type": "done", "response": "Hello", "session_id": "sess-stream"}

    mock_agent_service.run_turn_stream = fake_stream

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat/stream", json={
            "job_id": "job-agent",
            "message": "Stream this",
            "session_id": None,
        })

    assert response.status_code == 200
    assert "event: session" in response.text
    assert "event: tool_start" in response.text
    assert json.dumps({"type": "done", "response": "Hello", "session_id": "sess-stream"}) in response.text
