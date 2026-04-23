"""Redaction suggestion management service backed by blob storage."""

from collections.abc import Iterable
from typing import Optional
from datetime import datetime
from app.models import Suggestion


class RedactionService:
    """
    Redaction suggestion management service.

    Handles CRUD operations for suggestions and approval state management.
    Suggestions are PII/sensitive data identified for redaction.
    """

    def __init__(self, blob_client=None):
        """Initialize RedactionService."""
        self.blob_client = blob_client

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

    async def add_suggestions(self, job_id: str, suggestions_to_add: list[Suggestion]) -> int:
        """Append new suggestions in one blob read/write, skipping duplicates."""
        if not self.blob_client:
            raise Exception("Blob client not available for storing suggestions")

        if not suggestions_to_add:
            return 0

        try:
            suggestions = await self.blob_client.load_suggestions(job_id)
        except Exception:
            suggestions = []

        existing_keys = {
            self._dedupe_key(suggestion)
            for suggestion in suggestions
        }
        added = 0

        for suggestion in suggestions_to_add:
            key = self._dedupe_key(suggestion)
            if key in existing_keys:
                continue
            suggestions.append(suggestion)
            existing_keys.add(key)
            added += 1

        if added > 0:
            await self.blob_client.save_suggestions(job_id, suggestions)

        return added

    async def delete_suggestion(self, job_id: str, suggestion_id: str):
        """Delete a suggestion from the blob-backed suggestion set."""
        if not self.blob_client:
            raise Exception("Blob client not available for suggestion updates")

        suggestions = await self.blob_client.load_suggestions(job_id)
        filtered = [suggestion for suggestion in suggestions if suggestion.id != suggestion_id]
        if len(filtered) != len(suggestions):
            await self.blob_client.save_suggestions(job_id, filtered)

    def _dedupe_key(self, suggestion: Suggestion) -> tuple:
        rect_key = tuple(
            (
                round(rect.x0, 3),
                round(rect.y0, 3),
                round(rect.x1, 3),
                round(rect.y1, 3),
            )
            for rect in suggestion.rects
        )
        return (
            suggestion.page_num,
            suggestion.category.lower(),
            suggestion.text.strip().lower(),
            rect_key,
        )
