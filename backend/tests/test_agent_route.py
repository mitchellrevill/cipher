import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from redactor.main import app
from redactor.models import Job, JobStatus
from redactor.routes import jobs as jobs_module

@pytest.fixture(autouse=True)
def seed_job():
    jobs_module._jobs["job-agent"] = Job(job_id="job-agent", status=JobStatus.COMPLETE)
    yield
    jobs_module._jobs.pop("job-agent", None)

@pytest.mark.asyncio
async def test_chat_returns_response():
    with patch("redactor.routes.agent.run_agent_turn", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {
            "text": "I found 3 redactions.",
            "response_id": "resp-abc",
            "tool_calls": []
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/agent/chat", json={
                "job_id": "job-agent",
                "message": "What has been redacted?",
                "session_id": None,
                "previous_response_id": None
            })
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "response_id" in data
    assert "tool_calls" in data

@pytest.mark.asyncio
async def test_chat_returns_404_for_unknown_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/agent/chat", json={
            "job_id": "nonexistent",
            "message": "hello",
            "session_id": None,
            "previous_response_id": None
        })
    assert response.status_code == 404
