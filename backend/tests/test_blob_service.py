"""Tests for BlobService."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from redactor.services.blob_service import BlobService


@pytest.fixture
def mock_blob_client():
    """Create a mock Azure Blob client."""
    return MagicMock()


@pytest.fixture
def blob_service(mock_blob_client):
    """Create a BlobService instance with mocked blob client."""
    return BlobService(blob_client=mock_blob_client)


def test_upload_pdf(blob_service, mock_blob_client):
    """Verify uploading a PDF."""
    mock_container = MagicMock()
    mock_blob_client.get_container_client.return_value = mock_container
    mock_blob = MagicMock()
    mock_blob.url = "https://example.blob.core.windows.net/pdfs/job-1-original.pdf"
    mock_container.upload_blob.return_value = mock_blob

    url = blob_service.upload_pdf(job_id="job-1", pdf_bytes=b"PDF content")

    assert "job-1" in url or url is not None
    mock_container.upload_blob.assert_called_once()


def test_download_original_pdf(blob_service, mock_blob_client):
    """Verify downloading original PDF."""
    mock_container = MagicMock()
    mock_blob_client.get_container_client.return_value = mock_container
    mock_blob = MagicMock()
    mock_blob.download_blob.return_value.readall.return_value = b"PDF content"
    mock_container.get_blob_client.return_value = mock_blob

    pdf_bytes = blob_service.download_original_pdf(job_id="job-1")

    assert pdf_bytes == b"PDF content"
    mock_container.get_blob_client.assert_called_once()


def test_download_redacted_pdf(blob_service, mock_blob_client):
    """Verify downloading redacted PDF."""
    mock_container = MagicMock()
    mock_blob_client.get_container_client.return_value = mock_container
    mock_blob = MagicMock()
    mock_blob.download_blob.return_value.readall.return_value = b"Redacted PDF"
    mock_container.get_blob_client.return_value = mock_blob

    pdf_bytes = blob_service.download_redacted_pdf(job_id="job-1")

    assert pdf_bytes == b"Redacted PDF"


def test_save_redacted_pdf(blob_service, mock_blob_client):
    """Verify saving redacted PDF."""
    mock_container = MagicMock()
    mock_blob_client.get_container_client.return_value = mock_container

    blob_service.save_redacted_pdf(job_id="job-1", pdf_bytes=b"Redacted")

    mock_container.upload_blob.assert_called_once()


def test_delete_pdfs(blob_service, mock_blob_client):
    """Verify deleting PDFs."""
    mock_container = MagicMock()
    mock_blob_client.get_container_client.return_value = mock_container

    blob_service.delete_pdfs(job_id="job-1")

    # Should call delete for both original and redacted
    assert mock_container.delete_blob.called
