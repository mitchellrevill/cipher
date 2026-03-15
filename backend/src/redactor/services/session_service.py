"""Session persistence — stores agent conversation history in blob storage."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SessionService:
    """Read/write agent sessions to blob storage."""

    def __init__(self, blob_client):
        self.blob_client = blob_client

    async def save(self, session_id: str, payload: Any) -> None:
        await self.blob_client.upload_json(self._blob_name(session_id), payload)

    async def load(self, session_id: str) -> Any:
        payload = await self.blob_client.download_json(self._blob_name(session_id))
        if payload is None:
            return []
        return payload

    def _blob_name(self, session_id: str) -> str:
        return f"sessions/{session_id}.json"