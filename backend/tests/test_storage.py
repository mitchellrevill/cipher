import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from redactor.storage.blob import BlobStorageClient
from redactor.models import Suggestion, RedactionRect

@pytest.fixture
def blob_client():
    with patch("redactor.storage.blob.BlobServiceClient") as mock_svc, \
         patch("redactor.storage.blob.DefaultAzureCredential"):
        mock_container = MagicMock()
        mock_svc.return_value.get_container_client.return_value = mock_container
        client = BlobStorageClient(
            account_url="https://test.blob.core.windows.net",
            container="test"
        )
        yield client

@pytest.mark.asyncio
async def test_upload_pdf_calls_upload_blob(blob_client):
    mock_blob = MagicMock()
    mock_blob.upload_blob = AsyncMock()
    blob_client._container_client.get_blob_client.return_value = mock_blob
    await blob_client.upload_pdf("550e8400-e29b-41d4-a716-446655440000", b"pdf-bytes")
    mock_blob.upload_blob.assert_called_once_with(b"pdf-bytes", overwrite=True)

@pytest.mark.asyncio
async def test_save_suggestions_serialises_to_json(blob_client):
    from datetime import datetime
    mock_blob = MagicMock()
    mock_blob.upload_blob = AsyncMock()
    blob_client._container_client.get_blob_client.return_value = mock_blob
    suggestions = [
        Suggestion(id="1", job_id="job-1", text="John", category="Person", reasoning="PII",
                   context="", page_num=0, rects=[RedactionRect(x0=0,y0=0,x1=10,y1=10)], created_at=datetime.utcnow())
    ]
    await blob_client.save_suggestions("550e8400-e29b-41d4-a716-446655440000", suggestions)
    mock_blob.upload_blob.assert_called_once()
    # Verify JSON was passed
    call_args = mock_blob.upload_blob.call_args[0][0]
    parsed = json.loads(call_args)
    assert parsed[0]["text"] == "John"

@pytest.mark.asyncio
async def test_load_suggestions_deserialises_from_json(blob_client):
    from datetime import datetime
    now = datetime.utcnow()
    suggestion_data = [
        {"id": "1", "job_id": "job-1", "text": "John", "category": "Person", "reasoning": "PII",
         "context": "", "page_num": 0, "rects": [{"x0":0,"y0":0,"x1":10,"y1":10}],
         "approved": True, "source": "ai", "created_at": now.isoformat()}
    ]
    mock_stream = AsyncMock()
    mock_stream.readall = AsyncMock(return_value=json.dumps(suggestion_data).encode())
    mock_blob = MagicMock()
    mock_blob.download_blob = AsyncMock(return_value=mock_stream)
    blob_client._container_client.get_blob_client.return_value = mock_blob
    result = await blob_client.load_suggestions("550e8400-e29b-41d4-a716-446655440000")
    assert len(result) == 1
    assert result[0].text == "John"

def test_blob_name_rejects_invalid_job_id(blob_client):
    with pytest.raises(ValueError):
        blob_client._blob_name("../evil", "file.pdf")
    with pytest.raises(ValueError):
        blob_client._blob_name("not-a-uuid", "file.pdf")
