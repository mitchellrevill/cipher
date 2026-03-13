"""Integration tests for AgentService with the new agent framework."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from redactor.services.agent_service import AgentService


class MockOpenAIClient:
    """Mock Azure OpenAI client for testing."""

    class ChatCompletion:
        """Mock chat completion response."""

        def __init__(self, content, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls

    class Message:
        """Mock message."""

        def __init__(self, content, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls

    class Choice:
        """Mock choice."""

        def __init__(self, message):
            self.message = message

    class Response:
        """Mock response."""

        def __init__(self, content):
            self.choices = [MockOpenAIClient.Choice(MockOpenAIClient.Message(content))]

    async def create(self, **kwargs):
        """Mock create method for chat completions."""
        return self.Response("I'll help you with that document.")


@pytest.mark.asyncio
async def test_agent_service_create_session():
    """Test that AgentService can create a new chat session."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(filename="test.pdf")

    service = AgentService(
        oai_client=MockOpenAIClient(),
        job_service=mock_job_service,
        workspace_service=None,
    )

    # Create session
    session = await service.create_session("job123")

    assert session["id"]
    assert session["job_id"] == "job123"
    assert session["created_at"]
    assert session["messages"] == []
    assert session["last_response_id"] is None


@pytest.mark.asyncio
async def test_agent_service_save_message():
    """Test that AgentService can save messages to a session."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(filename="test.pdf")

    service = AgentService(
        oai_client=MockOpenAIClient(),
        job_service=mock_job_service,
        workspace_service=None,
    )

    # Create session
    session = await service.create_session("job123")

    # Save user message
    await service.save_message(session["id"], "user", "Search for PII")

    # Verify message was saved
    updated_session = await service.get_session(session["id"])
    assert len(updated_session["messages"]) == 1
    assert updated_session["messages"][0]["role"] == "user"
    assert updated_session["messages"][0]["text"] == "Search for PII"
    assert updated_session["messages"][0]["timestamp"]


@pytest.mark.asyncio
async def test_agent_service_full_flow():
    """Integration test: create session, save message, run turn, and get response."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(filename="test.pdf")

    service = AgentService(
        oai_client=MockOpenAIClient(),
        job_service=mock_job_service,
        workspace_service=None,
    )

    # Create session
    session = await service.create_session("job123")
    assert session["id"]

    # Save user message
    await service.save_message(session["id"], "user", "Search for PII")

    # Run turn
    response = await service.run_turn(
        job_id="job123",
        message="Search for PII",
        session_id=session["id"]
    )

    # Verify response structure
    assert response["text"]
    assert response["response_id"]
    assert "tool_calls" in response
    assert "directives" in response


@pytest.mark.asyncio
async def test_agent_service_run_turn_nonexistent_job():
    """Test that run_turn handles nonexistent jobs gracefully."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = None  # Job not found

    service = AgentService(
        oai_client=MockOpenAIClient(),
        job_service=mock_job_service,
        workspace_service=None,
    )

    # Create session
    session = await service.create_session("job123")

    # Run turn with nonexistent job
    response = await service.run_turn(
        job_id="nonexistent",
        message="Search for PII",
        session_id=session["id"]
    )

    # Should return error response
    assert "not found" in response["text"].lower()
    assert response["response_id"] is None
    assert response["tool_calls"] == []
    assert response["directives"] == []


@pytest.mark.asyncio
async def test_agent_service_multiple_turns():
    """Test that AgentService maintains conversation context across turns."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(filename="test.pdf")

    service = AgentService(
        oai_client=MockOpenAIClient(),
        job_service=mock_job_service,
        workspace_service=None,
    )

    # Create session
    session = await service.create_session("job123")

    # First turn
    await service.save_message(session["id"], "user", "What's in this document?")
    response1 = await service.run_turn(
        job_id="job123",
        message="What's in this document?",
        session_id=session["id"]
    )
    assert response1["text"]

    # Save assistant response
    await service.save_message(session["id"], "assistant", response1["text"])

    # Second turn
    await service.save_message(session["id"], "user", "Find PII")
    response2 = await service.run_turn(
        job_id="job123",
        message="Find PII",
        session_id=session["id"]
    )

    # Verify both responses exist
    assert response1["text"]
    assert response2["text"]
    assert response1["response_id"] != response2["response_id"]

    # Verify conversation history
    final_session = await service.get_session(session["id"])
    assert len(final_session["messages"]) >= 3


@pytest.mark.asyncio
async def test_agent_service_with_workspace_context():
    """Test that AgentService can handle workspace context in run_turn."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(filename="test.pdf")

    service = AgentService(
        oai_client=MockOpenAIClient(),
        job_service=mock_job_service,
        workspace_service=None,
    )

    # Create session
    session = await service.create_session("job123", workspace_id="workspace456")

    # Run turn with workspace context
    response = await service.run_turn(
        job_id="job123",
        message="Apply rules to document",
        workspace_id="workspace456",
        session_id=session["id"]
    )

    # Verify response and workspace context
    assert response["text"]
    assert response["response_id"]

    # Verify workspace is stored in session
    updated_session = await service.get_session(session["id"])
    assert updated_session["workspace_id"] == "workspace456"


@pytest.mark.asyncio
async def test_agent_service_initialization():
    """Test that AgentService initializes all components correctly."""
    mock_job_service = AsyncMock()
    mock_workspace_service = AsyncMock()

    service = AgentService(
        oai_client=MockOpenAIClient(),
        job_service=mock_job_service,
        workspace_service=mock_workspace_service,
    )

    # Verify all components are initialized
    assert service.oai_client is not None
    assert service.job_service is mock_job_service
    assert service.workspace_service is mock_workspace_service
    assert service.knowledge_base is not None
    assert service.tool_registry is not None
    assert service.agent_loop is not None
    assert service.sessions == {}
