from __future__ import annotations

from collections import Counter
from typing import Any

from redactor.services.job_service import JobService
from redactor.services.redaction_service import RedactionService
from redactor.services.rule_engine import RuleEngine
from redactor.services.workspace_service import WorkspaceService


class WorkspaceToolbox:
    """Workspace-aware tool implementations used by the redaction orchestrator."""

    def __init__(
        self,
        job_service: JobService,
        redaction_service: RedactionService,
        workspace_service: WorkspaceService | None = None,
        rule_engine: RuleEngine | None = None,
    ):
        self.job_service = job_service
        self.redaction_service = redaction_service
        self.workspace_service = workspace_service
        self.rule_engine = rule_engine or RuleEngine()

    async def list_workspaces(self, user_id: str = "user_default") -> list[dict[str, Any]]:
        if self.workspace_service is None:
            return []

        workspaces = await self.workspace_service.list_workspaces(user_id)
        return [
            {
                "id": workspace.get("id"),
                "name": workspace.get("name"),
                "doc_count": len(workspace.get("document_ids", [])),
                "rule_count": len(workspace.get("rule_ids", [])),
            }
            for workspace in workspaces
        ]

    async def get_workspace_state(self, workspace_id: str) -> dict[str, Any] | None:
        if self.workspace_service is None:
            return None
        return await self.workspace_service.get_workspace_state(workspace_id)

    async def get_document_context(self, doc_id: str) -> dict[str, Any] | None:
        job = await self.job_service.get_job(doc_id)
        if not job:
            return None

        summary = self._build_summary(job)
        return {
            "id": job.job_id,
            "title": job.filename,
            "status": job.status.value,
            "pages": job.page_count,
            "workspace_id": getattr(job, "workspace_id", None),
            "suggestions_count": len(job.suggestions),
            "approved": summary["approved"],
            "pending": summary["pending"],
            "by_category": summary["by_category"],
        }

    async def get_redaction_summary(self, doc_id: str) -> dict[str, Any] | None:
        job = await self.job_service.get_job(doc_id)
        if not job:
            return None
        summary = self._build_summary(job)
        summary["doc_id"] = job.job_id
        summary["filename"] = job.filename
        summary["status"] = job.status.value
        return summary

    async def search_document(
        self,
        query: str,
        doc_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        target_ids = await self._resolve_target_document_ids(doc_id=doc_id, workspace_id=workspace_id)
        query_lower = query.lower().strip()
        results: list[dict[str, Any]] = []

        for target_id in target_ids:
            job = await self.job_service.get_job(target_id)
            if not job:
                continue

            for suggestion in getattr(job, "suggestions", []):
                haystacks = [suggestion.text or "", suggestion.context or "", suggestion.reasoning or ""]
                if query_lower and not any(query_lower in haystack.lower() for haystack in haystacks):
                    continue

                results.append(
                    {
                        "document_id": target_id,
                        "filename": job.filename,
                        "page": self._to_viewer_page(suggestion.page_num),
                        "coords": [rect.model_dump() for rect in suggestion.rects],
                        "text": suggestion.text,
                        "context": suggestion.context,
                        "reasoning": suggestion.reasoning,
                        "category": suggestion.category,
                        "approved": suggestion.approved,
                        "suggestion_id": suggestion.id,
                    }
                )

        return sorted(results, key=lambda item: (item["document_id"], item["page"], item["text"] or ""))[:10]

    async def suggest_redactions(self, doc_id: str, context: str | None = None) -> dict[str, Any] | None:
        job = await self.job_service.get_job(doc_id)
        if not job:
            return None

        pending = [suggestion for suggestion in job.suggestions if not suggestion.approved]
        top_pending = sorted(pending, key=lambda suggestion: (suggestion.page_num, suggestion.category, suggestion.text))[:8]

        return {
            "doc_id": doc_id,
            "context": context,
            "pending_count": len(pending),
            "approved_count": len(job.suggestions) - len(pending),
            "suggestions": [
                {
                    "id": suggestion.id,
                    "text": suggestion.text,
                    "category": suggestion.category,
                    "page": self._to_viewer_page(suggestion.page_num),
                    "reason": suggestion.reasoning,
                }
                for suggestion in top_pending
            ],
        }

    async def add_redaction(self, doc_id: str, text: str, reason: str | None = None) -> dict[str, Any]:
        job = await self.job_service.get_job(doc_id)
        if not job:
            return {"status": "error", "message": "Document not found."}

        lowered = text.lower().strip()
        matching_ids = [
            suggestion.id
            for suggestion in job.suggestions
            if lowered and lowered in (suggestion.text or "").lower()
        ]

        if not matching_ids:
            return {
                "status": "needs-manual-selection",
                "message": "I could not find an existing suggestion to approve. Use draw mode for a brand-new area.",
                "reason": reason,
            }

        updated_count = await self.redaction_service.bulk_update_approvals(doc_id, True, suggestion_ids=matching_ids)
        return {
            "status": "approved",
            "message": f"Approved {updated_count} matching suggestion{'s' if updated_count != 1 else ''}.",
            "updated_count": updated_count,
            "suggestion_ids": matching_ids,
        }

    async def add_document_to_workspace(self, workspace_id: str, doc_id: str) -> dict[str, Any]:
        if self.workspace_service is None:
            return {"status": "error", "message": "Workspace support is unavailable."}
        workspace = await self.workspace_service.add_document(workspace_id, doc_id)
        return {
            "status": "ok",
            "docs_count": len(workspace.get("document_ids", [])),
            "workspace_id": workspace_id,
            "document_id": doc_id,
        }

    async def exclude_document(self, workspace_id: str, doc_id: str, reason: str) -> dict[str, Any]:
        if self.workspace_service is None:
            return {"status": "error", "message": "Workspace support is unavailable."}
        exclusion = await self.workspace_service.exclude_document(workspace_id, doc_id, reason)
        return {
            "status": "ok",
            "excluded_count": 1,
            "workspace_id": workspace_id,
            "document_id": doc_id,
            "reason": reason,
            "exclusion_id": exclusion.get("id"),
        }

    async def remove_exclusion(self, workspace_id: str, exclusion_id: str) -> dict[str, Any]:
        if self.workspace_service is None:
            return {"status": "error", "message": "Workspace support is unavailable."}
        await self.workspace_service.remove_exclusion(workspace_id, exclusion_id)
        return {"status": "ok", "workspace_id": workspace_id, "exclusion_id": exclusion_id}

    async def create_workspace_rule(self, workspace_id: str, rule_def: dict[str, Any]) -> dict[str, Any]:
        if self.workspace_service is None:
            return {"status": "error", "message": "Workspace support is unavailable."}

        created = await self.workspace_service.create_rule(
            workspace_id=workspace_id,
            pattern=rule_def["pattern"],
            category=rule_def["category"],
            confidence_threshold=rule_def.get("confidence_threshold", 0.8),
            applies_to=rule_def.get("applies_to"),
        )
        return {"status": "ok", "rule_id": created.get("id"), "rule": created}

    async def apply_batch_rule(
        self,
        workspace_id: str,
        rule_id: str,
        exclude_docs: list[str] | None = None,
    ) -> dict[str, Any]:
        if self.workspace_service is None:
            return {"status": "error", "message": "Workspace support is unavailable."}

        workspace = await self.workspace_service.get_workspace_state(workspace_id)
        if not workspace:
            return {"status": "error", "message": "Workspace not found."}

        rules = workspace.get("rules", [])
        rule = next((candidate for candidate in rules if candidate.get("id") == rule_id), None)
        if not rule:
            return {"status": "error", "message": "Rule not found."}

        excluded_doc_ids = {item.get("document_id") for item in workspace.get("exclusions", []) if item.get("document_id")}
        excluded_doc_ids.update(exclude_docs or [])
        jobs_by_id = {}
        for document in workspace.get("documents", []):
            document_id = document.get("id")
            if not document_id:
                continue
            jobs_by_id[document_id] = await self.job_service.get_job(document_id)

        result = await self.rule_engine.apply_rule(
            rule,
            jobs_by_id,
            redaction_service=self.redaction_service,
            excluded_doc_ids=excluded_doc_ids,
        )
        result["status"] = "ok"
        return result

    async def _resolve_target_document_ids(self, doc_id: str | None, workspace_id: str | None) -> list[str]:
        if doc_id:
            return [doc_id]
        if workspace_id and self.workspace_service is not None:
            workspace = await self.workspace_service.get_workspace_state(workspace_id)
            if workspace:
                return [document.get("id") for document in workspace.get("documents", []) if document.get("id")]
        return []

    def _build_summary(self, job) -> dict[str, Any]:
        approved = sum(1 for suggestion in job.suggestions if suggestion.approved)
        pending = len(job.suggestions) - approved
        by_category = Counter(suggestion.category for suggestion in job.suggestions)
        return {
            "approved": approved,
            "pending": pending,
            "by_category": dict(sorted(by_category.items())),
        }

    def _to_viewer_page(self, page_num: int) -> int:
        return page_num if page_num >= 1 else page_num + 1