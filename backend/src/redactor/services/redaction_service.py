"""
Redaction suggestion management service.

Manages CRUD operations for suggestions and approval state.
Integrates with Cosmos DB for suggestion persistence.
"""

from collections.abc import Iterable
from typing import Optional, List
from datetime import datetime
from redactor.models import Suggestion


class RedactionService:
    """
    Redaction suggestion management service.

    Handles CRUD operations for suggestions and approval state management.
    Suggestions are PII/sensitive data identified for redaction.
    """

    CONTAINER_NAME = "suggestions"
    PARTITION_KEY = "job_id"

    def __init__(self, cosmos_client, blob_client=None):
        """Initialize RedactionService with Cosmos DB and optional Blob Storage clients."""
        self.cosmos_client = cosmos_client
        self.blob_client = blob_client
        self.container = None

    async def _get_container(self):
        """Lazy-load container reference."""
        if self.container is None:
            # Will be set up when DB is initialized (Task 9)
            pass
        return self.container

    async def save_suggestions(self, job_id: str, suggestions: List[dict]) -> List[dict]:
        """
        Save multiple suggestions for a job.

        Args:
            job_id: Job identifier
            suggestions: List of suggestion dicts

        Returns:
            List of saved suggestions
        """
        saved = []
        now = datetime.utcnow()
        for sugg in suggestions:
            sugg["job_id"] = job_id
            sugg["created_at"] = sugg.get("created_at", now.isoformat())
            sugg["updated_at"] = now.isoformat()
            result = self.cosmos_client.create_item(body=sugg)
            saved.append(result)
        return saved

    async def get_suggestions(self, job_id: str) -> List[Suggestion]:
        """
        Get all suggestions for a job.

        Args:
            job_id: Job identifier

        Returns:
            List of suggestions
        """
        try:
            query = f"SELECT * FROM c WHERE c.job_id = '{job_id}'"
            results = list(self.cosmos_client.query_items(query=query))
            return [self._doc_to_suggestion(doc) for doc in results]
        except Exception:
            return []

    async def toggle_approval(self, job_id: str, suggestion_id: str, approved: bool):
        """
        Toggle suggestion approval status.

        Args:
            job_id: Job identifier
            suggestion_id: Suggestion identifier
            approved: New approval status
        """
        if not self.blob_client:
            raise Exception("Blob client not available for redaction updates")

        # Load suggestions from blob storage
        suggestions = await self.blob_client.load_suggestions(job_id)

        # Find and update the suggestion
        for sugg in suggestions:
            if sugg.id == suggestion_id:
                sugg.approved = approved
                sugg.updated_at = datetime.utcnow()
                break

        # Save updated suggestions back to blob storage
        await self.blob_client.save_suggestions(job_id, suggestions)

    async def bulk_update_approvals(
        self,
        job_id: str,
        approved: bool,
        suggestion_ids: Iterable[str] | None = None,
    ) -> int:
        """
        Update approval status for many suggestions in a single blob read/write.

        Args:
            job_id: Job identifier
            approved: New approval status
            suggestion_ids: Optional iterable of suggestion identifiers to update.
                When omitted, all suggestions that do not already match the target
                approval state are updated.

        Returns:
            Number of suggestions updated
        """
        if not self.blob_client:
            raise Exception("Blob client not available for redaction updates")

        suggestions = await self.blob_client.load_suggestions(job_id)
        suggestion_id_set = set(suggestion_ids) if suggestion_ids is not None else None
        updated_count = 0
        updated_at = datetime.utcnow()

        for suggestion in suggestions:
            matches_target = suggestion_id_set is None or suggestion.id in suggestion_id_set
            if not matches_target or suggestion.approved == approved:
                continue

            suggestion.approved = approved
            suggestion.updated_at = updated_at
            updated_count += 1

        if updated_count > 0:
            await self.blob_client.save_suggestions(job_id, suggestions)

        return updated_count

    async def add_manual_suggestion(self, job_id: str, suggestion: Suggestion):
        """
        Add a manually created suggestion.

        Args:
            job_id: Job identifier
            suggestion: Suggestion to add
        """
        if not self.blob_client:
            raise Exception("Blob client not available for storing manual suggestions")

        # Load existing suggestions from blob storage
        try:
            suggestions = await self.blob_client.load_suggestions(job_id)
        except Exception:
            # If no suggestions exist yet, start with empty list
            suggestions = []

        # Add the new manual suggestion to the list
        suggestions.append(suggestion)

        # Save all suggestions back to blob storage
        await self.blob_client.save_suggestions(job_id, suggestions)

    async def delete_suggestion(self, job_id: str, suggestion_id: str):
        """
        Delete a suggestion.

        Args:
            job_id: Job identifier
            suggestion_id: Suggestion identifier
        """
        self.cosmos_client.delete_item(item=suggestion_id, partition_key=job_id)

    def _doc_to_suggestion(self, doc: dict) -> Suggestion:
        """Convert Cosmos DB document to Suggestion model."""
        created_at = doc.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = doc.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        # Convert rect dicts to RedactionRect objects
        from redactor.models import RedactionRect
        rects = [RedactionRect(**r) for r in doc.get("rects", [])]

        return Suggestion(
            id=doc.get("id"),
            job_id=doc.get("job_id"),
            text=doc.get("text"),
            category=doc.get("category"),
            reasoning=doc.get("reasoning"),
            context=doc.get("context"),
            page_num=doc.get("page_num"),
            rects=rects,
            approved=doc.get("approved", False),
            source=doc.get("source", "ai"),
            created_at=created_at,
            updated_at=updated_at
        )
