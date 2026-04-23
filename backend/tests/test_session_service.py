import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.session_service import SessionService


def make_blob():
    blob = MagicMock()
    blob.upload_json = AsyncMock()
    blob.download_json = AsyncMock(return_value=[{"role": "user", "content": "hello"}])
    return blob


@pytest.mark.asyncio
async def test_save_session_uploads_to_blob():
    blob = make_blob()
    service = SessionService(blob_client=blob)
    messages = [{"role": "user", "content": "hello"}]

    await service.save("sess-1", messages)

    blob.upload_json.assert_called_once_with("sessions/sess-1.json", messages)


@pytest.mark.asyncio
async def test_load_session_returns_messages():
    blob = make_blob()
    service = SessionService(blob_client=blob)

    result = await service.load("sess-1")

    assert result == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_load_session_missing_returns_empty():
    blob = make_blob()
    blob.download_json.return_value = None
    service = SessionService(blob_client=blob)

    result = await service.load("missing")

    assert result == []