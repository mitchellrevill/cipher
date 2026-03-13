from typing import Any, Dict, Optional
from redactor.agent.tools.base import Tool, ToolResult


class SearchTool(Tool):
    """Search for text in workspace documents."""

    name = "search_document"
    description = "Search for text in the current document or workspace. Returns matching locations with page numbers and coordinates."

    def __init__(self, workspace_toolbox=None):
        self.workspace_toolbox = workspace_toolbox

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
                    "description": "Optional document ID to search in (searches workspace by default)"
                }
            },
            "required": ["query"]
        }

    async def execute(self, query: str, doc_id: Optional[str] = None, **kwargs) -> ToolResult:
        """Execute search."""
        if not self.workspace_toolbox:
            return ToolResult(
                success=False,
                error="Workspace toolbox not configured"
            )

        try:
            results = await self.workspace_toolbox.search_document(
                query=query,
                doc_id=doc_id
            )

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "count": len(results)
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )
