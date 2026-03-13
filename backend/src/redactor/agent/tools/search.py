from typing import Any, Dict, Optional
from redactor.agent.tools.base import Tool, ToolResult


class SearchTool(Tool):
    """Search for text in document suggestions."""

    name = "search_document"
    description = "Search for text in the current document suggestions. Returns matching locations with page numbers and coordinates."

    def __init__(self, job_service=None):
        self.job_service = job_service

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for"
                },
                "doc_id": {
                    "type": "string",
                    "description": "Document ID to search in"
                }
            },
            "required": ["query", "doc_id"]
        }

    async def execute(self, query: str, doc_id: str, **kwargs) -> ToolResult:
        """Execute search in document suggestions."""
        if not self.job_service:
            return ToolResult(
                success=False,
                error="Job service not configured"
            )

        try:
            job = await self.job_service.get_job(doc_id)
            if not job:
                return ToolResult(
                    success=False,
                    error=f"Document '{doc_id}' not found"
                )

            query_lower = query.lower().strip()
            results = []

            # Search through suggestions
            for suggestion in getattr(job, "suggestions", []):
                haystacks = [
                    suggestion.text or "",
                    suggestion.context or "",
                    suggestion.reasoning or ""
                ]
                if query_lower and not any(query_lower in haystack.lower() for haystack in haystacks):
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

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "document_id": doc_id,
                    "results": results,
                    "count": len(results)
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )
