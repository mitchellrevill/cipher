import json
import logging
from typing import Annotated
from agent_framework import tool
from pydantic import Field

logger = logging.getLogger(__name__)


class DocumentTools:
    """Tools for searching within a single redaction document."""

    def __init__(self, job_service):
        self.job_service = job_service

    @tool(approval_mode="never_require")
    async def search_document(
        self,
        query: Annotated[str, Field(description="Text to search for in redaction suggestions")],
        doc_id: Annotated[str, Field(description="Document ID to search in")],
    ) -> str:
        """Search for text in the current document's redaction suggestions."""
        if not self.job_service:
            return "Error: job service not configured"

        try:
            job = await self.job_service.get_job(doc_id)
            if not job:
                return f"Error: document '{doc_id}' not found"

            query_lower = query.lower().strip()
            if not query_lower:
                return "Error: query must not be empty"
            results = []
            for suggestion in getattr(job, "suggestions", []):
                haystacks = [
                    suggestion.text or "",
                    suggestion.context or "",
                    suggestion.reasoning or "",
                ]
                if query_lower and not any(query_lower in h.lower() for h in haystacks):
                    continue
                results.append({
                    "id": suggestion.id,
                    "text": suggestion.text,
                    "category": suggestion.category,
                    "page": suggestion.page_num,
                    "context": suggestion.context,
                    "reasoning": suggestion.reasoning,
                    "approved": suggestion.approved,
                })

            return json.dumps({
                "query": query,
                "document_id": doc_id,
                "results": results,
                "count": len(results),
            })
        except Exception as e:
            logger.exception("Error in search_document")
            return f"Error: search failed — {e}"
