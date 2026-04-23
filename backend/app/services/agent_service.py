"""AI agent service for conversational redaction assistance."""

import asyncio
from contextlib import suppress
import contextvars
import logging
import uuid
from typing import Any, AsyncIterator, Optional

from app.agent.tools.search import DocumentTools
from app.agent.tools.suggestions import SuggestionTools
from app.agent.tools.workspace import WorkspaceTools
from app.agent.knowledge_base import KnowledgeBase
from app.services.job_service import JobService
from app.services.redaction_service import RedactionService
from app.services.rule_engine import RuleEngine
from app.services.session_service import SessionService
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)
_active_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("active_agent_session_id", default=None)

SYSTEM_PROMPT = (
    "You are an intelligent PDF redaction assistant. "
    "Help users understand document redaction suggestions, search within documents, "
    "and manage workspace-level rules and exclusions using the available tools. "
    "Be precise, concise, and explicit about limitations.\n\n"
    "Rule creation guidelines:\n"
    "- Create one rule per distinct term or pattern. Never combine multiple terms into a single rule using regex alternation (e.g. do NOT use 'Spouse|Partner|Husband|Wife'). "
    "Each term must be its own separate rule with its own create_rule call.\n"
    "- After creating each rule, immediately call apply_rule with the new rule's ID to apply it across all workspace documents. "
    "Do not wait or ask for confirmation — always apply the rule right after creating it.\n\n"
    "Bulk approval guidelines:\n"
    "- Always call preview_bulk_approval before apply_bulk_approval. Present the preview "
    "results to the user and wait for explicit confirmation before applying.\n"
    "- When applying bulk changes, use the exact same filter arguments used in the preview."
)

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
        session_service: Optional[SessionService] = None,
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
        self.session_service = session_service
        self._session_state: dict[str, dict[str, Any]] = {}
        self._runtime_sessions: dict[str, Any] = {}
        self._hydrated_sessions: set[str] = set()
        self._event_queues: dict[str, asyncio.Queue] = {}

        document_tools = DocumentTools(job_service=job_service, event_emitter=self._emit_tool_event)
        workspace_tools = WorkspaceTools(
            workspace_service=workspace_service,
            job_service=job_service,
            redaction_service=redaction_service,
            rule_engine=rule_engine,
            event_emitter=self._emit_tool_event,
        )
        suggestion_tools = SuggestionTools(
            job_service=job_service,
            redaction_service=redaction_service,
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
                suggestion_tools.approve_suggestion,
                suggestion_tools.delete_suggestion,
                suggestion_tools.create_suggestion,
                workspace_tools.search_workspace,
                workspace_tools.preview_bulk_approval,
                workspace_tools.apply_bulk_approval,
                workspace_tools.bulk_create_suggestions,
            ],
        )

    def _emit_tool_event(self, *, event_type: str, tool_name: str, summary: Optional[str] = None) -> None:
        session_id = _active_session_id.get()
        if not session_id:
            return

        queue = self._event_queues.get(session_id)
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
        session = self.agent.create_session()
        context = await self._build_context_summary(job_id, workspace_id)
        state = {
            "session_id": session.session_id,
            "job_id": job_id,
            "workspace_id": workspace_id,
            "context": context,
            "context_injected": False,
            "messages": [],
        }
        self._runtime_sessions[session.session_id] = session
        self._hydrated_sessions.add(session.session_id)
        await self._save_state(session.session_id, state)
        return session.session_id

    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        state = await self._get_state(session_id)
        if not state:
            return None

        return {
            **state,
            "session": self._get_or_create_runtime_session(session_id, state),
        }

    async def _get_state(self, session_id: str) -> Optional[dict[str, Any]]:
        if session_id in self._session_state:
            return self._session_state[session_id]

        if not self.session_service:
            return None

        payload = await self.session_service.load(session_id)
        if not payload:
            return None

        if isinstance(payload, dict):
            state = payload
        else:
            state = {
                "session_id": session_id,
                "job_id": None,
                "workspace_id": None,
                "context": "",
                "context_injected": True,
                "messages": payload,
            }

        state.setdefault("session_id", session_id)
        state.setdefault("messages", [])
        state.setdefault("context", "")
        state.setdefault("context_injected", False)
        self._session_state[session_id] = state
        return state

    async def _save_state(self, session_id: str, state: dict[str, Any]) -> None:
        self._session_state[session_id] = state
        if self.session_service:
            await self.session_service.save(session_id, state)

    def _get_or_create_runtime_session(self, session_id: str, state: dict[str, Any]):
        session = self._runtime_sessions.get(session_id)
        if session is not None:
            return session

        session = self.agent.create_session()
        self._runtime_sessions[session_id] = session
        if not state.get("messages"):
            self._hydrated_sessions.add(session_id)
        return session

    def _history_prompt(self, messages: list[dict[str, str]]) -> str:
        if not messages:
            return ""
        lines = [f"{message.get('role', 'user').upper()}: {message.get('content', '')}" for message in messages]
        return "[Conversation so far]\n" + "\n".join(lines) + "\n[/Conversation so far]"

    async def _prepare_turn(
        self,
        session_id: str,
        message: str,
        workspace_id: Optional[str] = None,
    ) -> tuple[Optional[dict[str, Any]], Optional[Any], Optional[str], Optional[str]]:
        session_state = await self._get_state(session_id)
        if not session_state:
            return None, None, "Session not found"

        runtime_session = self._get_or_create_runtime_session(session_id, session_state)

        if workspace_id and workspace_id != session_state.get("workspace_id"):
            session_state["workspace_id"] = workspace_id
            session_state["context"] = await self._build_context_summary(session_state["job_id"], workspace_id)
            session_state["context_injected"] = False

        payload_parts = []
        if not session_state.get("context_injected") and session_state.get("context"):
            payload_parts.append(f"[Context]\n{session_state['context']}\n[/Context]")
            session_state["context_injected"] = True

        if session_id not in self._hydrated_sessions:
            history_prompt = self._history_prompt(session_state.get("messages", []))
            if history_prompt:
                payload_parts.append(history_prompt)
            self._hydrated_sessions.add(session_id)

        payload_parts.append(message)
        payload = "\n\n".join(part for part in payload_parts if part)

        return session_state, runtime_session, payload, None

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
            session_state, runtime_session, payload, error = await self._prepare_turn(session_id, message, workspace_id)
            if error or not session_state or runtime_session is None or payload is None:
                return {"text": error or "Session not found"}

            result = await self.agent.run(payload, session=runtime_session)
            text = getattr(result, "text", None)
            if text is None:
                value = getattr(result, "value", None)
                text = str(value) if value is not None else str(result)
            session_state.setdefault("messages", []).extend(
                [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": str(text)},
                ]
            )
            await self._save_state(session_id, session_state)
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
        session_state, runtime_session, payload, error = await self._prepare_turn(session_id, message, workspace_id)
        if error or not session_state or runtime_session is None or payload is None:
            yield {"type": "error", "error": error or "Session not found"}
            return

        queue: asyncio.Queue = asyncio.Queue()
        self._event_queues[session_id] = queue

        async def consume_stream() -> None:
            token = _active_session_id.set(session_id)
            try:
                stream = self.agent.run(payload, session=runtime_session, stream=True)
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
                session_state.setdefault("messages", []).extend(
                    [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": str(text)},
                    ]
                )
                await self._save_state(session_id, session_state)
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
            self._event_queues.pop(session_id, None)
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
