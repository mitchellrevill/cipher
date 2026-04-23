import asyncio
import json
import logging
from typing import Annotated, Awaitable, Callable, Optional
from agent_framework import tool
from pydantic import Field

from app.pdf.processor import PDFProcessor

logger = logging.getLogger(__name__)


class WorkspaceTools:
    """Tools for managing workspace state, rules, and document exclusions."""

    def __init__(self, workspace_service, job_service=None, redaction_service=None, rule_engine=None, event_emitter: Optional[Callable[..., None]] = None):
        self.workspace_service = workspace_service
        self.job_service = job_service
        self.redaction_service = redaction_service
        self.rule_engine = rule_engine
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
            if "applied_count" in payload:
                return f"Applied {payload.get('applied_count', 0)} matches"
            if "count" in payload and "workspace_id" in payload:
                return f"Returned {payload['count']} items for {payload['workspace_id']}"
            if "id" in payload:
                return f"Updated {payload['id']}"
            if "workspace" in payload:
                return f"Loaded workspace {payload['workspace'].get('id', 'unknown')}"

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

    async def _require_workspace(self, workspace_id: str):
        if not self.workspace_service:
            return None, "Error: workspace service not configured"

        state = await self.workspace_service.get_workspace_state(workspace_id)
        if not state:
            return None, f"Error: workspace '{workspace_id}' not found"
        return state, None

    def _filter_suggestions(self, suggestions, approved: bool, category=None, text_pattern=None):
        """Return suggestions that would be updated given target state and filters."""
        results = []
        for suggestion in suggestions:
            if suggestion.approved == approved:
                continue
            if category and suggestion.category.lower() != category.lower():
                continue
            if text_pattern and text_pattern.lower() not in suggestion.text.lower():
                continue
            results.append(suggestion)
        return results

    @tool(approval_mode="never_require")
    async def get_workspace_state(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
    ) -> str:
        """Return the current workspace documents, rules, and exclusions."""
        async def action() -> str:
            try:
                state, error = await self._require_workspace(workspace_id)
                if error:
                    return error
                return json.dumps({
                    "workspace": state,
                    "document_count": len(state.get("documents", [])),
                    "rule_count": len(state.get("rules", [])),
                    "exclusion_count": len(state.get("exclusions", [])),
                })
            except Exception as e:
                logger.exception("Error in get_workspace_state")
                return f"Error: {e}"

        return await self._run_tool("get_workspace_state", action)

    @tool(approval_mode="never_require")
    async def create_rule(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        category: Annotated[str, Field(description="Redaction category (e.g. 'PII', 'CreditCard')")],
        pattern: Annotated[str, Field(description="Pattern or description of what to redact")],
        confidence_threshold: Annotated[float, Field(description="Confidence threshold for the workspace rule")] = 0.8,
    ) -> str:
        """Create a new redaction rule for a category in the workspace."""
        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            try:
                result = await self.workspace_service.create_rule(
                    workspace_id=workspace_id,
                    pattern=pattern,
                    category=category,
                    confidence_threshold=confidence_threshold,
                )
                return json.dumps(result)
            except Exception as e:
                logger.exception("Error in create_rule")
                return f"Error: {e}"

        return await self._run_tool("create_rule", action)

    @tool(approval_mode="never_require")
    async def apply_rule(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        rule_id: Annotated[str, Field(description="Workspace rule identifier to apply")],
    ) -> str:
        """Apply a saved workspace rule across all non-excluded documents."""
        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            if not self.job_service or not self.redaction_service or not self.rule_engine:
                return "Error: rule application services are not configured"
            try:
                workspace, error = await self._require_workspace(workspace_id)
                if error:
                    return error

                rules = await self.workspace_service.get_rules(workspace_id)
                rule = next((item for item in rules if item.get("id") == rule_id), None)
                if not rule:
                    return f"Error: rule '{rule_id}' not found in workspace '{workspace_id}'"

                jobs_by_id = {}
                for document in workspace.get("documents", []):
                    job = await self.job_service.get_job(document["id"])
                    if job:
                        jobs_by_id[document["id"]] = job

                excluded_doc_ids = {item.get("document_id") for item in workspace.get("exclusions", []) if item.get("document_id")}
                result = await self.rule_engine.apply_rule(
                    rule,
                    jobs_by_id,
                    redaction_service=self.redaction_service,
                    excluded_doc_ids=excluded_doc_ids,
                )
                return json.dumps(result)
            except Exception as e:
                logger.exception("Error in apply_rule")
                return f"Error: {e}"

        return await self._run_tool("apply_rule", action)

    @tool(approval_mode="never_require")
    async def exclude_document(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        document_id: Annotated[str, Field(description="Document to exclude from workspace automation")],
        reason: Annotated[str, Field(description="Reason for exclusion")] = "Excluded from automation",
    ) -> str:
        """Exclude a document from workspace rules and automation."""
        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            try:
                result = await self.workspace_service.exclude_document(workspace_id, document_id, reason)
                return json.dumps(result)
            except Exception as e:
                logger.exception("Error in exclude_document")
                return f"Error: {e}"

        return await self._run_tool("exclude_document", action)

    @tool(approval_mode="never_require")
    async def list_workspace_rules(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
    ) -> str:
        """List all rules configured for a workspace."""
        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            try:
                rules = await self.workspace_service.get_rules(workspace_id)
                return json.dumps({
                    "workspace_id": workspace_id,
                    "count": len(rules),
                    "rules": rules,
                })
            except Exception as e:
                logger.exception("Error in list_workspace_rules")
                return f"Error: {e}"

        return await self._run_tool("list_workspace_rules", action)

    @tool(approval_mode="never_require")
    async def list_workspace_exclusions(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
    ) -> str:
        """List all exclusions configured for a workspace."""
        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            try:
                exclusions = await self.workspace_service.get_exclusions(workspace_id)
                return json.dumps({
                    "workspace_id": workspace_id,
                    "count": len(exclusions),
                    "exclusions": exclusions,
                })
            except Exception as e:
                logger.exception("Error in list_workspace_exclusions")
                return f"Error: {e}"

        return await self._run_tool("list_workspace_exclusions", action)

    @tool(approval_mode="never_require")
    async def add_document_to_workspace(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        document_id: Annotated[str, Field(description="Document/job identifier to add to the workspace")],
    ) -> str:
        """Add an existing document to a workspace."""
        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            try:
                result = await self.workspace_service.add_document(workspace_id, document_id)
                return json.dumps(result)
            except Exception as e:
                logger.exception("Error in add_document_to_workspace")
                return f"Error: {e}"

        return await self._run_tool("add_document_to_workspace", action)

    @tool(approval_mode="never_require")
    async def remove_document_from_workspace(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        document_id: Annotated[str, Field(description="Document/job identifier to remove from the workspace")],
    ) -> str:
        """Remove a document from a workspace."""
        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            try:
                result = await self.workspace_service.remove_document(workspace_id, document_id)
                return json.dumps(result)
            except Exception as e:
                logger.exception("Error in remove_document_from_workspace")
                return f"Error: {e}"

        return await self._run_tool("remove_document_from_workspace", action)

    @tool(approval_mode="never_require")
    async def remove_exclusion(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        exclusion_id: Annotated[str, Field(description="Exclusion identifier to remove")],
    ) -> str:
        """Remove an exclusion from a workspace so the document participates in automation again."""
        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            try:
                result = await self.workspace_service.remove_exclusion(workspace_id, exclusion_id)
                return json.dumps(result)
            except Exception as e:
                logger.exception("Error in remove_exclusion")
                return f"Error: {e}"

        return await self._run_tool("remove_exclusion", action)

    @tool(approval_mode="never_require")
    async def search_workspace(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        query: Annotated[str, Field(description="Text to search for across all workspace documents")],
        limit: Annotated[int, Field(description="Maximum matches to return per document")] = 10,
    ) -> str:
        """Search raw PDF text across all non-excluded workspace documents."""

        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            if not query.strip():
                return "Error: query cannot be empty"
            try:
                import re

                state, error = await self._require_workspace(workspace_id)
                if error:
                    return error

                capped_limit = max(1, min(limit, 50))
                excluded_ids = {item.get("document_id") for item in state.get("exclusions", []) if item.get("document_id")}
                docs = [document for document in state.get("documents", []) if document["id"] not in excluded_ids]
                blob_client = getattr(self.job_service, "blob_client", None)

                async def search_one(doc_id: str) -> dict:
                    filename = None
                    try:
                        job = await self.job_service.get_job(doc_id)
                        filename = getattr(job, "filename", None) if job else None
                        if not blob_client:
                            return {"doc_id": doc_id, "filename": filename, "error": "blob client unavailable"}
                        pdf_bytes = await blob_client.download_original_pdf(doc_id)
                        processor = PDFProcessor(pdf_bytes)
                        matches_raw = processor.search_text(re.escape(query.strip()))
                        matches = [
                            {"text": match["text"], "page": match["page_num"], "context": match.get("context", "")}
                            for match in matches_raw[:capped_limit]
                        ]
                        return {"doc_id": doc_id, "filename": filename, "count": len(matches), "matches": matches}
                    except Exception as exc:
                        return {"doc_id": doc_id, "filename": filename, "error": str(exc)}

                results = list(await asyncio.gather(*[search_one(document["id"]) for document in docs]))
                return json.dumps(
                    {
                        "workspace_id": workspace_id,
                        "query": query,
                        "documents_searched": len(docs),
                        "documents_with_matches": sum(1 for item in results if item.get("count", 0) > 0),
                        "documents_with_errors": sum(1 for item in results if "error" in item),
                        "results": results,
                    }
                )
            except Exception as e:
                logger.exception("Error in search_workspace")
                return f"Error: {e}"

        return await self._run_tool("search_workspace", action)

    @tool(approval_mode="never_require")
    async def preview_bulk_approval(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        approved: Annotated[bool, Field(description="Target approval state")],
        category: Annotated[
            Optional[str],
            Field(description="Filter by suggestion category (case-insensitive exact match)"),
        ] = None,
        text_pattern: Annotated[
            Optional[str],
            Field(description="Filter by suggestion text (case-insensitive substring)"),
        ] = None,
    ) -> str:
        """Dry-run showing what would change for a bulk approval operation."""

        async def action() -> str:
            if not self.workspace_service:
                return "Error: workspace service not configured"
            try:
                state, error = await self._require_workspace(workspace_id)
                if error:
                    return error

                excluded_ids = {item.get("document_id") for item in state.get("exclusions", []) if item.get("document_id")}
                docs = [document for document in state.get("documents", []) if document["id"] not in excluded_ids]
                jobs = await asyncio.gather(*[self.job_service.get_job(document["id"]) for document in docs])

                total = 0
                by_document = []
                for job in jobs:
                    if not job:
                        continue
                    matches = self._filter_suggestions(getattr(job, "suggestions", []), approved, category, text_pattern)
                    total += len(matches)
                    by_document.append(
                        {
                            "doc_id": job.job_id,
                            "filename": getattr(job, "filename", None),
                            "would_change": len(matches),
                            "sample_texts": [suggestion.text for suggestion in matches[:5]],
                        }
                    )

                return json.dumps(
                    {
                        "workspace_id": workspace_id,
                        "target_approved": approved,
                        "total_would_change": total,
                        "by_document": by_document,
                    }
                )
            except Exception as e:
                logger.exception("Error in preview_bulk_approval")
                return f"Error: {e}"

        return await self._run_tool("preview_bulk_approval", action)

    @tool(approval_mode="never_require")
    async def apply_bulk_approval(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        approved: Annotated[bool, Field(description="Target approval state")],
        category: Annotated[
            Optional[str],
            Field(description="Filter by suggestion category (case-insensitive exact match)"),
        ] = None,
        text_pattern: Annotated[
            Optional[str],
            Field(description="Filter by suggestion text (case-insensitive substring)"),
        ] = None,
    ) -> str:
        """Apply approval changes across all non-excluded workspace documents."""

        async def action() -> str:
            if not self.workspace_service or not self.redaction_service:
                return "Error: workspace service or redaction service not configured"
            try:
                state, error = await self._require_workspace(workspace_id)
                if error:
                    return error

                excluded_ids = {item.get("document_id") for item in state.get("exclusions", []) if item.get("document_id")}
                docs = [document for document in state.get("documents", []) if document["id"] not in excluded_ids]
                jobs = await asyncio.gather(*[self.job_service.get_job(document["id"]) for document in docs])

                total_updated = 0
                by_document = []
                for job in jobs:
                    if not job:
                        continue
                    matches = self._filter_suggestions(getattr(job, "suggestions", []), approved, category, text_pattern)
                    if not matches:
                        by_document.append(
                            {
                                "doc_id": job.job_id,
                                "filename": getattr(job, "filename", None),
                                "updated": 0,
                            }
                        )
                        continue

                    suggestion_ids = [suggestion.id for suggestion in matches]
                    updated = await self.redaction_service.bulk_update_approvals(job.job_id, approved, suggestion_ids)
                    total_updated += updated
                    by_document.append(
                        {
                            "doc_id": job.job_id,
                            "filename": getattr(job, "filename", None),
                            "updated": updated,
                        }
                    )

                return json.dumps(
                    {
                        "workspace_id": workspace_id,
                        "approved": approved,
                        "total_updated": total_updated,
                        "by_document": by_document,
                    }
                )
            except Exception as e:
                logger.exception("Error in apply_bulk_approval")
                return f"Error: {e}"

        return await self._run_tool("apply_bulk_approval", action)

    @tool(approval_mode="never_require")
    async def bulk_create_suggestions(
        self,
        workspace_id: Annotated[str, Field(description="Workspace identifier")],
        text: Annotated[str, Field(description="Text to search for and create suggestions from")],
        category: Annotated[str, Field(description="Redaction category for the created suggestions")],
        reasoning: Annotated[Optional[str], Field(description="Why this text should be redacted")] = None,
    ) -> str:
        """Create matching suggestions in every non-excluded workspace document containing the text."""

        async def action() -> str:
            if not self.workspace_service or not self.redaction_service:
                return "Error: workspace service or redaction service not configured"
            if not text.strip():
                return "Error: text cannot be empty"
            try:
                import re
                import uuid as _uuid
                from datetime import datetime as _dt

                from app.models import Suggestion

                state, error = await self._require_workspace(workspace_id)
                if error:
                    return error

                excluded_ids = {item.get("document_id") for item in state.get("exclusions", []) if item.get("document_id")}
                docs = [document for document in state.get("documents", []) if document["id"] not in excluded_ids]
                blob_client = getattr(self.job_service, "blob_client", None)
                reason = reasoning or "Added by agent across workspace"
                total_added = 0
                by_document = []

                for document in docs:
                    doc_id = document["id"]
                    filename = None
                    try:
                        job = await self.job_service.get_job(doc_id)
                        filename = getattr(job, "filename", None) if job else None
                        if not blob_client:
                            by_document.append(
                                {
                                    "doc_id": doc_id,
                                    "filename": filename,
                                    "added": 0,
                                    "skipped_dedupe": 0,
                                    "no_match": True,
                                }
                            )
                            continue

                        pdf_bytes = await blob_client.download_original_pdf(doc_id)
                        processor = PDFProcessor(pdf_bytes)
                        matches_raw = processor.search_text(re.escape(text.strip()))
                        if not matches_raw:
                            by_document.append(
                                {
                                    "doc_id": doc_id,
                                    "filename": filename,
                                    "added": 0,
                                    "skipped_dedupe": 0,
                                    "no_match": True,
                                }
                            )
                            continue

                        suggestions_to_add = [
                            Suggestion(
                                id=str(_uuid.uuid4()),
                                job_id=doc_id,
                                text=match["text"],
                                category=category,
                                page_num=match["page_num"],
                                reasoning=reason,
                                context="",
                                rects=[],
                                source="agent",
                                approved=False,
                                created_at=_dt.utcnow(),
                            )
                            for match in matches_raw
                        ]
                        added = await self.redaction_service.add_suggestions(doc_id, suggestions_to_add)
                        skipped = len(suggestions_to_add) - added
                        total_added += added
                        by_document.append(
                            {
                                "doc_id": doc_id,
                                "filename": filename,
                                "added": added,
                                "skipped_dedupe": skipped,
                                "no_match": False,
                            }
                        )
                    except Exception as exc:
                        by_document.append(
                            {
                                "doc_id": doc_id,
                                "filename": filename,
                                "added": 0,
                                "skipped_dedupe": 0,
                                "no_match": False,
                                "error": str(exc),
                            }
                        )

                return json.dumps(
                    {
                        "workspace_id": workspace_id,
                        "text": text,
                        "category": category,
                        "total_added": total_added,
                        "by_document": by_document,
                    }
                )
            except Exception as e:
                logger.exception("Error in bulk_create_suggestions")
                return f"Error: {e}"

        return await self._run_tool("bulk_create_suggestions", action)
