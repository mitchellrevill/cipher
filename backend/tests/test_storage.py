import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from redactor.storage.blob import BlobStorageClient
from redactor.models import Suggestion, RedactionRect

@pytest.fixture
def blob_client():
    with patch("redactor.storage.blob.DefaultAzureCredential") as mock_cred, \
         patch("redactor.storage.blob.BlobServiceClient") as mock_svc:
        mock_cred.return_value = MagicMock()
        mock_svc.return_value = MagicMock()
        client = BlobStorageClient(
            account_url="https://test.blob.core.windows.net",
            container="test"
        )
        yield client

@pytest.mark.asyncio
async def test_upload_pdf_calls_upload_blob(blob_client):
    blob_client._container_client.get_blob_client.return_value.upload_blob = AsyncMock()
    await blob_client.upload_pdf("job-123", b"pdf-bytes")
    blob_client._container_client.get_blob_client.assert_called_once()

@pytest.mark.asyncio
async def test_save_suggestions_serialises_to_json(blob_client):
    blob_client._container_client.get_blob_client.return_value.upload_blob = AsyncMock()
    suggestions = [
        Suggestion(id="1", text="John", category="Person", reasoning="PII",
                   context="", page_num=0, rects=[RedactionRect(x0=0,y0=0,x1=10,y1=10)])
    ]
    await blob_client.save_suggestions("job-123", suggestions)
    blob_client._container_client.get_blob_client.return_value.upload_blob.assert_called_once()

@pytest.mark.asyncio
async def test_load_suggestions_deserialises_from_json(blob_client):
    import json
    suggestion_data = [
        {"id": "1", "text": "John", "category": "Person", "reasoning": "PII",
         "context": "", "page_num": 0, "rects": [{"x0":0,"y0":0,"x1":10,"y1":10}],
         "approved": True, "source": "ai"}
    ]
    mock_stream = AsyncMock()
    mock_stream.readall = AsyncMock(return_value=json.dumps(suggestion_data).encode())
    blob_client._container_client.get_blob_client.return_value.download_blob = AsyncMock(return_value=mock_stream)
    result = await blob_client.load_suggestions("job-123")
    assert len(result) == 1
    assert result[0].text == "John"
