import json
import logging
import uuid
from datetime import datetime
from typing import Annotated, Awaitable, Callable, Optional

from agent_framework import tool
from pydantic import Field

from backend.app.models import Suggestion

logger = logging.getLogger(__name__)


class SuggestionTools:
    """Tools for mutating individual redaction suggestions."""

    def __init__(self, job_service, redaction_service=None, event_emitter: Optional[Callable[..., None]] = None):
        self.job_service = job_service
        self.redaction_service = redaction_service
        self.event_emitter = event_emitter

    def _emit(self, event_type: str, tool_name: str, summary: Optional[str] = None):
        if self.event_emitter:
            self.event_emitter(event_type=event_type, tool_name=tool_name, summary=summary)

    def _summarize_result(self, result: str) -> str:
        if result.startswith("Error:"):
            return result

        try:
            payload = json.loads(result)
        except Exception:
            return result[:160]

        if isinstance(payload, dict):
            status = payload.get("status", "")
            suggestion_id = payload.get("suggestion_id", "")
            if status and suggestion_id:
                return f"{status} suggestion {suggestion_id}"

        return result[:160]

    async def _run_tool(self, tool_name: str, action: Callable[[], Awaitable[str]]) -> str:
        self._emit("tool_start", tool_name)
        try:
            result = await action()
            self._emit("tool_result", tool_name, self._summarize_result(result))
            return result
        except Exception as exc:
            self._emit("tool_error", tool_name, str(exc))
            raise

    async def _get_job_and_suggestion(self, doc_id: str, suggestion_id: str):
        """Load job; return (job, suggestion, error_string)."""
        if not self.job_service:
            return None, None, "Error: job service not configured"

        job = await self.job_service.get_job(doc_id)
        if not job:
            return None, None, f"Error: document '{doc_id}' not found"

        suggestion = next((item for item in getattr(job, "suggestions", []) if item.id == suggestion_id), None)
        if not suggestion:
            return job, None, f"Error: suggestion not found: '{suggestion_id}' in document '{doc_id}'"

        return job, suggestion, None

    @tool(approval_mode="never_require")
    async def approve_suggestion(
        self,
        doc_id: Annotated[str, Field(description="Document ID containing the suggestion")],
        suggestion_id: Annotated[str, Field(description="Suggestion ID to approve or reject")],
        approved: Annotated[bool, Field(description="True to approve, False to reject")],
    ) -> str:
        """Toggle the approval state of a single suggestion in a document."""

        async def action() -> str:
            if not self.redaction_service:
                return "Error: redaction service not configured"
            try:
                _, _, error = await self._get_job_and_suggestion(doc_id, suggestion_id)
                if error:
                    return error
                await self.redaction_service.toggle_approval(doc_id, suggestion_id, approved)
                return json.dumps(
                    {
                        "doc_id": doc_id,
                        "suggestion_id": suggestion_id,
                        "approved": approved,
                        "status": "updated",
                    }
                )
            except Exception as exc:
                logger.exception("Error in approve_suggestion")
                return f"Error: {exc}"

        return await self._run_tool("approve_suggestion", action)

    @tool(approval_mode="never_require")
    async def delete_suggestion(
        self,
        doc_id: Annotated[str, Field(description="Document ID containing the suggestion")],
        suggestion_id: Annotated[str, Field(description="Suggestion ID to permanently remove")],
    ) -> str:
        """Permanently remove a suggestion from a document."""

        async def action() -> str:
            if not self.redaction_service:
                return "Error: redaction service not configured"
            try:
                _, _, error = await self._get_job_and_suggestion(doc_id, suggestion_id)
                if error:
                    return error
                await self.redaction_service.delete_suggestion(doc_id, suggestion_id)
                return json.dumps({"doc_id": doc_id, "suggestion_id": suggestion_id, "status": "deleted"})
            except Exception as exc:
                logger.exception("Error in delete_suggestion")
                return f"Error: {exc}"

        return await self._run_tool("delete_suggestion", action)

    @tool(approval_mode="never_require")
    async def create_suggestion(
        self,
        doc_id: Annotated[str, Field(description="Document ID to add the suggestion to")],
        text: Annotated[str, Field(description="Text to be redacted")],
        category: Annotated[str, Field(description="Redaction category, e.g. 'PII', 'Financial'")],
        page_num: Annotated[int, Field(description="Zero-based page number where the text appears")],
        reasoning: Annotated[Optional[str], Field(description="Why this text should be redacted")] = None,
    ) -> str:
        """Manually add a redaction suggestion the pipeline missed."""

        async def action() -> str:
            if not self.redaction_service:
                return "Error: redaction service not configured"
            try:
                suggestion = Suggestion(
                    id=str(uuid.uuid4()),
                    job_id=doc_id,
                    text=text,
                    category=category,
                    page_num=page_num,
                    reasoning=reasoning or "Manually created by agent",
                    context="",
                    rects=[],
                    source="agent",
                    approved=False,
                    created_at=datetime.utcnow(),
                )
                await self.redaction_service.add_manual_suggestion(doc_id, suggestion)
                return json.dumps({"doc_id": doc_id, "suggestion_id": suggestion.id, "status": "created"})
            except Exception as exc:
                logger.exception("Error in create_suggestion")
                return f"Error: {exc}"

        return await self._run_tool("create_suggestion", action)