"""Tests for AgentService."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
import redactor.services.agent_service as agent_service_module
from redactor.services.agent_service import AgentService
from redactor.services.job_service import JobService
from redactor.services.workspace_service import WorkspaceService


class FakeResponseStream:
    def __init__(self, updates, final_text="streamed final"):
        self._updates = updates
        self._final_text = final_text

    def __aiter__(self):
        self._iterator = iter(self._updates)
        return self

    async def __anext__(self):
        try:
            value = next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc
        await asyncio.sleep(0)
        return value

    async def get_final_response(self):
        return MagicMock(text=self._final_text)


@pytest.fixture
def mock_oai_client():
    """Create a mock Agent Framework client."""
    client = MagicMock()
    framework_agent = MagicMock()
    framework_agent.create_session = MagicMock(return_value=MagicMock(session_id="sess-123"))
    framework_agent.run = AsyncMock(return_value=MagicMock(text="3 redactions were found."))
    client.as_agent = MagicMock(return_value=framework_agent)
    client.framework_agent = framework_agent
    return client


@pytest.fixture
def mock_job_service():
    """Create a mock JobService."""
    service = AsyncMock(spec=JobService)
    return service


@pytest.fixture
def mock_workspace_service():
    """Create a mock WorkspaceService."""
    service = AsyncMock(spec=WorkspaceService)
    service.get_workspace_state.return_value = {
        "id": "ws-1",
        "documents": [{"id": "job-1"}],
        "rules": [{"id": "rule-1"}],
        "exclusions": [],
    }
    return service


@pytest.fixture
def agent_service(mock_oai_client, mock_job_service, mock_workspace_service):
    """Create an AgentService instance with mocked dependencies."""
    agent_service_module._sessions.clear()
    service = AgentService(
        oai_client=mock_oai_client,
        job_service=mock_job_service,
        workspace_service=mock_workspace_service,
    )
    yield service
    agent_service_module._sessions.clear()


@pytest.mark.asyncio
async def test_create_session(agent_service, mock_oai_client):
    """Verify creating a framework-backed chat session."""
    session_id = await agent_service.create_session(job_id="job-1")

    assert session_id == "sess-123"
    session = await agent_service.get_session(session_id)
    assert session is not None
    assert session["job_id"] == "job-1"
    assert session["context_injected"] is False


@pytest.mark.asyncio
async def test_get_session(agent_service, mock_oai_client):
    """Verify retrieving a chat session."""
    session_id = await agent_service.create_session(job_id="job-1")

    retrieved = await agent_service.get_session(session_id=session_id)

    assert retrieved is not None
    assert retrieved["job_id"] == "job-1"
    assert retrieved["session"].session_id == session_id


@pytest.mark.asyncio
async def test_get_session_not_found(agent_service):
    """Verify retrieving a non-existent session returns None."""
    session = await agent_service.get_session(session_id="nonexistent-sess")

    assert session is None


@pytest.mark.asyncio
async def test_run_turn_injects_context_on_first_message(agent_service, mock_oai_client):
    """Verify first turn includes session context before calling the framework agent."""
    session_id = await agent_service.create_session(job_id="job-1", workspace_id="ws-1")

    result = await agent_service.run_turn(session_id=session_id, message="What was redacted?")

    assert result is not None
    assert "text" in result
    assert result["text"] == "3 redactions were found."

    run_args = mock_oai_client.framework_agent.run.await_args
    assert run_args.kwargs["session"].session_id == session_id
    assert "[Context]" in run_args.args[0]
    assert "Current document/job: job-1." in run_args.args[0]
    assert "Workspace: ws-1." in run_args.args[0]


@pytest.mark.asyncio
async def test_run_turn_second_message_skips_context_prefix(agent_service, mock_oai_client):
    """Verify subsequent turns reuse the framework session without reinjecting prefix context."""
    session_id = await agent_service.create_session(job_id="job-1")

    await agent_service.run_turn(session_id=session_id, message="First turn")
    await agent_service.run_turn(session_id=session_id, message="Second turn")

    second_call = mock_oai_client.framework_agent.run.await_args_list[1]
    assert second_call.args[0] == "Second turn"


@pytest.mark.asyncio
async def test_session_store_shared_across_instances(mock_oai_client, mock_job_service, mock_workspace_service):
    """Verify module-level session store persists across AgentService instances."""
    agent_service_module._sessions.clear()
    service_one = AgentService(
        oai_client=mock_oai_client,
        job_service=mock_job_service,
        workspace_service=mock_workspace_service,
    )
    session_id = await service_one.create_session(job_id="job-1")

    service_two = AgentService(
        oai_client=mock_oai_client,
        job_service=mock_job_service,
        workspace_service=mock_workspace_service,
    )
    session = await service_two.get_session(session_id)

    assert session is not None
    assert session["job_id"] == "job-1"
    agent_service_module._sessions.clear()


@pytest.mark.asyncio
async def test_run_turn_error_handling(agent_service, mock_oai_client):
    """Verify run_turn handles errors gracefully."""
    session_id = await agent_service.create_session(job_id="job-1")
    mock_oai_client.framework_agent.run.side_effect = Exception("Agent error")

    result = await agent_service.run_turn(session_id=session_id, message="What was redacted?")

    assert result is not None
    assert "text" in result
    assert "Error processing request" in result["text"]


@pytest.mark.asyncio
async def test_run_turn_stream_emits_session_and_text_events(agent_service, mock_oai_client):
    session_id = await agent_service.create_session(job_id="job-1")
    mock_oai_client.framework_agent.run = MagicMock(
        return_value=FakeResponseStream(
            [MagicMock(text="Hello "), MagicMock(text="world")],
            final_text="Hello world",
        )
    )

    events = [event async for event in agent_service.run_turn_stream(session_id=session_id, message="hi")]

    assert events[0]["type"] == "session"
    assert any(event["type"] == "text_delta" and event["delta"] == "Hello " for event in events)
    assert any(event["type"] == "done" and event["response"] == "Hello world" for event in events)


@pytest.mark.asyncio
async def test_run_turn_stream_emits_tool_events(agent_service, mock_oai_client):
    session_id = await agent_service.create_session(job_id="job-1")

    class ToolEmittingStream:
        def __init__(self):
            self._emitted = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._emitted:
                raise StopAsyncIteration

            self._emitted = True
            agent_service._emit_tool_event(event_type="tool_start", tool_name="search_document", summary=None)
            agent_service._emit_tool_event(
                event_type="tool_result",
                tool_name="search_document",
                summary="Found 2 results",
            )
            raise StopAsyncIteration

        async def get_final_response(self):
            return MagicMock(text="done")

    mock_oai_client.framework_agent.run = MagicMock(return_value=ToolEmittingStream())

    events = [event async for event in agent_service.run_turn_stream(session_id=session_id, message="hi")]

    assert any(event["type"] == "tool_start" and event["tool_name"] == "search_document" for event in events)
    assert any(event["type"] == "tool_result" and event["summary"] == "Found 2 results" for event in events)


