import uuid
from redactor.models import Suggestion
from redactor.services.job_service import JobService


def make_tools(job_id: str, job_service: JobService) -> dict:
    """Return a dict of callable tools scoped to a specific job.

    These are async functions that will be called by the agent service.
    They retrieve job data from JobService instead of in-memory storage.
    """

    async def get_redaction_summary() -> dict:
        """Return the current redaction state for the job."""
        job = await job_service.get_job(job_id)
        if not job:
            return {"error": "Job not found"}
        approved = [s for s in job.suggestions if s.approved]
        by_category: dict[str, int] = {}
        for s in approved:
            by_category[s.category] = by_category.get(s.category, 0) + 1
        return {
            "total_approved": len(approved),
            "total_suggestions": len(job.suggestions),
            "by_category": by_category
        }

    async def add_redaction(text: str, reason: str) -> str:
        """Add a new redaction for `text` across all pages."""
        job = await job_service.get_job(job_id)
        if not job:
            return "Job not found"
        added = 0
        for suggestion in job.suggestions:
            if suggestion.text.lower() == text.lower():
                suggestion.approved = True
                added += 1
        if added == 0:
            job.suggestions.append(Suggestion(
                id=str(uuid.uuid4()), text=text, category="AgentAdded",
                reasoning=reason, context="", page_num=0, rects=[], approved=True, source="agent"
            ))
        return f"Redaction added for '{text}' ({added} existing occurrences approved)"

    async def remove_redaction(redaction_id: str) -> str:
        """Remove a suggestion by ID."""
        job = await job_service.get_job(job_id)
        if not job:
            return "Job not found"
        before = len(job.suggestions)
        job.suggestions = [s for s in job.suggestions if s.id != redaction_id]
        removed = before - len(job.suggestions)
        return f"removed {removed} suggestion(s) with id '{redaction_id}'"

    async def add_exception(text: str) -> str:
        """Unapprove all suggestions matching `text`."""
        job = await job_service.get_job(job_id)
        if not job:
            return "Job not found"
        count = 0
        for s in job.suggestions:
            if s.text.lower() == text.lower():
                s.approved = False
                count += 1
        return f"Added exception for '{text}': {count} suggestion(s) unapproved"

    async def search_document(query: str) -> list[dict]:
        """Find all suggestions whose text matches the query."""
        job = await job_service.get_job(job_id)
        if not job:
            return []
        query_lower = query.lower()
        return [
            {"id": s.id, "text": s.text, "page_num": s.page_num + 1, "approved": s.approved}
            for s in job.suggestions
            if query_lower in s.text.lower() or query_lower in s.context.lower()
        ]

    return {
        "get_redaction_summary": get_redaction_summary,
        "add_redaction": add_redaction,
        "remove_redaction": remove_redaction,
        "add_exception": add_exception,
        "search_document": search_document,
    }
