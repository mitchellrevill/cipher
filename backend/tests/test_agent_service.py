"""Tests for AgentService."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from redactor.services.agent_service import AgentService
from redactor.services.job_service import JobService
from redactor.services.workspace_service import WorkspaceService


@pytest.fixture
def mock_oai_client():
    """Create a mock Azure OpenAI client."""
    return AsyncMock()


@pytest.fixture
def mock_job_service():
    """Create a mock JobService."""
    service = AsyncMock(spec=JobService)
    return service


@pytest.fixture
def mock_workspace_service():
    """Create a mock WorkspaceService."""
    return AsyncMock(spec=WorkspaceService)


@pytest.fixture
def agent_service(mock_oai_client, mock_job_service, mock_workspace_service):
    """Create an AgentService instance with mocked dependencies."""
    return AgentService(
        oai_client=mock_oai_client,
        job_service=mock_job_service,
        workspace_service=mock_workspace_service,
    )


@pytest.mark.asyncio
async def test_create_session(agent_service, mock_oai_client):
    """Verify creating a chat session."""
    session = await agent_service.create_session(job_id="job-1")

    assert session is not None
    assert session["job_id"] == "job-1"
    assert session["id"] is not None
    assert session["created_at"] is not None
    assert session["messages"] == []


@pytest.mark.asyncio
async def test_get_session(agent_service, mock_oai_client):
    """Verify retrieving a chat session."""
    # First create a session
    session = await agent_service.create_session(job_id="job-1")
    session_id = session["id"]

    # Then get it
    retrieved = await agent_service.get_session(session_id=session_id)

    assert retrieved is not None
    assert retrieved["job_id"] == "job-1"
    assert retrieved["id"] == session_id


@pytest.mark.asyncio
async def test_get_session_not_found(agent_service):
    """Verify retrieving a non-existent session returns None."""
    session = await agent_service.get_session(session_id="nonexistent-sess")

    assert session is None


@pytest.mark.asyncio
async def test_save_message(agent_service):
    """Verify saving a message to session."""
    # Create a session first
    session = await agent_service.create_session(job_id="job-1")
    session_id = session["id"]

    # Save a message
    await agent_service.save_message(
        session_id=session_id,
        role="user",
        text="What was redacted?"
    )

    # Retrieve and verify
    retrieved = await agent_service.get_session(session_id=session_id)
    assert len(retrieved["messages"]) == 1
    assert retrieved["messages"][0]["role"] == "user"
    assert retrieved["messages"][0]["text"] == "What was redacted?"


@pytest.mark.asyncio
async def test_run_turn(agent_service, mock_oai_client, mock_job_service):
    """Verify running an agent turn with OpenAI."""
    # Setup mocks
    mock_job_service.get_job.return_value = MagicMock(
        filename="test.pdf",
        job_id="job-1"
    )

    mock_oai_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(
                content="3 redactions were found.",
                tool_calls=None
            ))]
        )
    )

    result = await agent_service.run_turn(
        job_id="job-1",
        message="What was redacted?",
        previous_response_id=None
    )

    assert result is not None
    assert "text" in result
    assert "response_id" in result
    assert "tool_calls" in result
    assert result["text"] == "3 redactions were found."
    assert result["response_id"] is not None


@pytest.mark.asyncio
async def test_run_turn_error_handling(agent_service, mock_oai_client, mock_job_service):
    """Verify run_turn handles errors gracefully."""
    # Setup mocks to raise an error
    mock_job_service.get_job.side_effect = Exception("Database error")

    result = await agent_service.run_turn(
        job_id="job-1",
        message="What was redacted?",
        previous_response_id=None
    )

    assert result is not None
    assert "text" in result
    assert "Error processing request" in result["text"]
    assert result["response_id"] is None


@pytest.mark.asyncio
async def test_run_turn_uses_orchestrator(agent_service, mock_job_service, mock_workspace_service):
    """Verify run_turn delegates to orchestrator when configured."""
    mock_job_service.get_job.return_value = MagicMock(filename="test.pdf", job_id="job-1")
    mock_workspace_service.get_workspace_state.return_value = {
        "id": "ws-1",
        "name": "Workspace",
        "documents": [],
        "rules": [],
        "exclusions": [],
    }
    orchestrator = AsyncMock()
    orchestrator.run_turn = AsyncMock(return_value={
        "text": "Workspace-aware response",
        "response_id": "resp-1",
        "tool_calls": [],
        "directives": [],
    })
    agent_service.orchestrator = orchestrator
    session = await agent_service.create_session("job-1", workspace_id="ws-1")

    result = await agent_service.run_turn(
        job_id="job-1",
        message="Apply the workspace rules",
        workspace_id="ws-1",
        session_id=session["id"],
    )

    assert result["text"] == "Workspace-aware response"
    orchestrator.run_turn.assert_called_once()
