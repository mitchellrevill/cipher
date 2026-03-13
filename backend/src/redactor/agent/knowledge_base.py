from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class KnowledgeBase:
    """Manages workspace context and knowledge for the agent."""

    def __init__(self, workspace_service=None, cache_ttl_seconds: int = 300):
        """
        Args:
            workspace_service: Service to load workspace state
            cache_ttl_seconds: How long to cache context (default 5 min)
        """
        self.workspace_service = workspace_service
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: Dict[str, tuple[Any, datetime]] = {}

    async def get_workspace_context(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get workspace context (documents, rules, exclusions).

        Returns cached context if available and not expired.
        Returns None if workspace doesn't exist.
        """
        # Check cache
        if workspace_id in self._cache:
            context, cached_at = self._cache[workspace_id]
            if datetime.utcnow() - cached_at < self.cache_ttl:
                return context

        # Load from service
        if not self.workspace_service:
            return None

        context = await self.workspace_service.get_workspace_state(workspace_id)

        # Cache result
        if context:
            self._cache[workspace_id] = (context, datetime.utcnow())

        return context

    def invalidate_cache(self, workspace_id: Optional[str] = None) -> None:
        """Invalidate cache for a workspace or all workspaces."""
        if workspace_id:
            self._cache.pop(workspace_id, None)
        else:
            self._cache.clear()
