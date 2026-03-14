"""AI agent service for conversational redaction assistance."""

import asyncio
from contextlib import suppress
import contextvars
import logging
from typing import Any, AsyncIterator, Optional

from redactor.agent.tools.search import DocumentTools
from redactor.agent.tools.workspace import WorkspaceTools
from redactor.agent.knowledge_base import KnowledgeBase
from redactor.services.job_service import JobService
from redactor.services.redaction_service import RedactionService
from redactor.services.rule_engine import RuleEngine
from redactor.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)
_active_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("active_agent_session_id", default=None)

SYSTEM_PROMPT = (
    "You are an intelligent PDF redaction assistant. "
    "Help users understand document redaction suggestions, search within documents, "
    "and manage workspace-level rules and exclusions using the available tools. "
    "Be precise, concise, and explicit about limitations."
)

_sessions: dict[str, dict[str, Any]] = {}


class AgentService:
    """
    AI agent service for conversational assistance with document redaction.

    Manages chat sessions and uses an agent loop with tool execution for
    context-aware responses about redaction decisions.
    """

    def __init__(
        self,
        oai_client,
        job_service: JobService,
        workspace_service: Optional[WorkspaceService] = None,
        redaction_service: Optional[RedactionService] = None,
        rule_engine: Optional[RuleEngine] = None,
        knowledge_base: Optional[KnowledgeBase] = None,
    ):
        """
        Initialize AgentService with agent framework components.

        Args:
            oai_client: Agent Framework Azure OpenAI client
            job_service: JobService for accessing job context
            workspace_service: WorkspaceService for managing workspaces
            redaction_service: RedactionService for updating approvals during rule application
            rule_engine: RuleEngine for resolving and applying workspace rules
            knowledge_base: Shared KnowledgeBase for workspace context
        """
        self.oai_client = oai_client
        self.job_service = job_service
        self.workspace_service = workspace_service
        self.redaction_service = redaction_service
        self.rule_engine = rule_engine
        self.knowledge_base = knowledge_base or KnowledgeBase(workspace_service=workspace_service)

        document_tools = DocumentTools(job_service=job_service, event_emitter=self._emit_tool_event)
        workspace_tools = WorkspaceTools(
            workspace_service=workspace_service,
            job_service=job_service,
            redaction_service=redaction_service,
            rule_engine=rule_engine,
            event_emitter=self._emit_tool_event,
        )

        self.agent = oai_client.as_agent(
            name="RedactionAssistant",
            instructions=SYSTEM_PROMPT,
            tools=[
                document_tools.search_document,
                document_tools.get_document_summary,
                document_tools.list_document_suggestions,
                document_tools.get_suggestion_details,
                workspace_tools.get_workspace_state,
                workspace_tools.create_rule,
                workspace_tools.apply_rule,
                workspace_tools.exclude_document,
                workspace_tools.list_workspace_rules,
                workspace_tools.list_workspace_exclusions,
                workspace_tools.add_document_to_workspace,
                workspace_tools.remove_document_from_workspace,
                workspace_tools.remove_exclusion,
            ],
        )

    def _emit_tool_event(self, *, event_type: str, tool_name: str, summary: Optional[str] = None) -> None:
        session_id = _active_session_id.get()
        if not session_id:
            return

        session_data = _sessions.get(session_id)
        if not session_data:
            return

        queue: asyncio.Queue | None = session_data.get("event_queue")
        if not queue:
            return

        queue.put_nowait(
            {
                "type": event_type,
                "tool_name": tool_name,
                "summary": summary,
            }
        )

    async def _build_context_summary(self, job_id: str, workspace_id: Optional[str] = None) -> str:
        """Build concise per-session context for the agent."""
        summary = f"Current document/job: {job_id}."
        if not workspace_id:
            return summary

        try:
            workspace_context = await self.knowledge_base.get_workspace_context(workspace_id)
        except Exception:
            logger.exception("Failed to load workspace context")
            return f"{summary} Workspace: {workspace_id}."

        if not workspace_context:
            return f"{summary} Workspace: {workspace_id}."

        documents = workspace_context.get("documents", [])
        rules = workspace_context.get("rules", [])
        exclusions = workspace_context.get("exclusions", [])
        return (
            f"{summary} Workspace: {workspace_id}. "
            f"Documents: {len(documents)}. "
            f"Rules: {len(rules)}. "
            f"Exclusions: {len(exclusions)}."
        )

    async def create_session(self, job_id: str, workspace_id: Optional[str] = None) -> str:
        """
        Create a new chat session for a job.

        Args:
            job_id: Job identifier

        Returns:
            Framework-backed session identifier
        """
        session = self.agent.create_session()
        context = await self._build_context_summary(job_id, workspace_id)
        _sessions[session.session_id] = {
            "session": session,
            "job_id": job_id,
            "workspace_id": workspace_id,
            "context": context,
            "context_injected": False,
        }
        return session.session_id

    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """
        Get a chat session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session dict or None if not found
        """
        return _sessions.get(session_id)

    async def _prepare_turn(
        self,
        session_id: str,
        message: str,
        workspace_id: Optional[str] = None,
    ) -> tuple[Optional[dict[str, Any]], Optional[str], Optional[str]]:
        session_data = _sessions.get(session_id)
        if not session_data:
            return None, None, "Session not found"

        if workspace_id and workspace_id != session_data.get("workspace_id"):
            session_data["workspace_id"] = workspace_id
            session_data["context"] = await self._build_context_summary(session_data["job_id"], workspace_id)
            session_data["context_injected"] = False

        payload = message
        if not session_data.get("context_injected"):
            payload = f"[Context]\n{session_data['context']}\n[/Context]\n\n{message}"
            session_data["context_injected"] = True

        return session_data, payload, None

    async def run_turn(
        self,
        session_id: str,
        message: str,
        workspace_id: Optional[str] = None,
    ) -> dict[str, str]:
        """
        Run an agent turn using Microsoft Agent Framework.

        Args:
            session_id: Session identifier for context and continuity
            message: User message
            workspace_id: Optional workspace ID for context

        Returns:
            Dict with assistant text
        """
        try:
            session_data, payload, error = await self._prepare_turn(session_id, message, workspace_id)
            if error or not session_data or payload is None:
                return {"text": error or "Session not found"}

            result = await self.agent.run(payload, session=session_data["session"])
            text = getattr(result, "text", None)
            if text is None:
                value = getattr(result, "value", None)
                text = str(value) if value is not None else str(result)
            return {"text": str(text)}

        except Exception:
            logger.exception("Error in agent turn")
            return {"text": "Error processing request"}

    async def run_turn_stream(
        self,
        session_id: str,
        message: str,
        workspace_id: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        session_data, payload, error = await self._prepare_turn(session_id, message, workspace_id)
        if error or not session_data or payload is None:
            yield {"type": "error", "error": error or "Session not found"}
            return

        queue: asyncio.Queue = asyncio.Queue()
        session_data["event_queue"] = queue

        async def consume_stream() -> None:
            token = _active_session_id.set(session_id)
            try:
                stream = self.agent.run(payload, session=session_data["session"], stream=True)
                if not hasattr(stream, "__aiter__"):
                    stream = await stream

                async for update in stream:
                    delta = getattr(update, "text", "")
                    if delta:
                        await queue.put({"type": "text_delta", "delta": str(delta)})

                final_response = await stream.get_final_response()
                text = getattr(final_response, "text", None)
                if text is None:
                    value = getattr(final_response, "value", None)
                    text = str(value) if value is not None else str(final_response)
                await queue.put({"type": "done", "response": str(text), "session_id": session_id})
            except Exception:
                logger.exception("Error in streaming agent turn")
                await queue.put({"type": "error", "error": "Error processing request"})
            finally:
                _active_session_id.reset(token)
                await queue.put({"type": "__complete__"})

        task = asyncio.create_task(consume_stream())

        try:
            yield {"type": "session", "session_id": session_id}
            while True:
                event = await queue.get()
                if event.get("type") == "__complete__":
                    break
                yield event
        finally:
            session_data.pop("event_queue", None)
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
