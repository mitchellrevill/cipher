"""
Azure Blob Storage service for PDF lifecycle management.

Manages upload, download, and deletion of PDF files.
Maintains separate blobs for original and redacted PDFs.
"""

from typing import Optional
from azure.storage.blob import BlobServiceClient


class BlobService:
    """
    Azure Blob Storage service for PDF lifecycle management.

    Handles upload, download, and deletion of PDF files.
    Maintains separate containers for original and redacted PDFs.
    """

    CONTAINER_NAME = "pdfs"

    def __init__(self, blob_client: BlobServiceClient):
        """Initialize BlobService with Azure Blob Storage client."""
        self.blob_client = blob_client
        self.container = None

    def _get_container(self):
        """Get reference to the PDFs container."""
        if self.container is None:
            self.container = self.blob_client.get_container_client(self.CONTAINER_NAME)
        return self.container

    def upload_pdf(self, job_id: str, pdf_bytes: bytes) -> str:
        """
        Upload original PDF.

        Args:
            job_id: Job identifier
            pdf_bytes: PDF file content

        Returns:
            URL of uploaded blob
        """
        blob_name = f"{job_id}-original.pdf"
        container = self._get_container()

        blob = container.upload_blob(
            name=blob_name,
            data=pdf_bytes,
            overwrite=True
        )

        return blob.url if hasattr(blob, 'url') else f"https://{blob_name}"

    def download_original_pdf(self, job_id: str) -> Optional[bytes]:
        """
        Download original PDF.

        Args:
            job_id: Job identifier

        Returns:
            PDF file content or None if not found
        """
        try:
            blob_name = f"{job_id}-original.pdf"
            container = self._get_container()
            blob = container.get_blob_client(blob_name)
            return blob.download_blob().readall()
        except Exception:
            return None

    def download_redacted_pdf(self, job_id: str) -> Optional[bytes]:
        """
        Download redacted PDF.

        Args:
            job_id: Job identifier

        Returns:
            Redacted PDF file content or None if not found
        """
        try:
            blob_name = f"{job_id}-redacted.pdf"
            container = self._get_container()
            blob = container.get_blob_client(blob_name)
            return blob.download_blob().readall()
        except Exception:
            return None

    def save_redacted_pdf(self, job_id: str, pdf_bytes: bytes):
        """
        Save redacted PDF.

        Args:
            job_id: Job identifier
            pdf_bytes: Redacted PDF content
        """
        blob_name = f"{job_id}-redacted.pdf"
        container = self._get_container()

        container.upload_blob(
            name=blob_name,
            data=pdf_bytes,
            overwrite=True
        )

    def delete_pdfs(self, job_id: str):
        """
        Delete both original and redacted PDFs.

        Args:
            job_id: Job identifier
        """
        container = self._get_container()

        try:
            container.delete_blob(f"{job_id}-original.pdf")
        except Exception:
            pass

        try:
            container.delete_blob(f"{job_id}-redacted.pdf")
        except Exception:
            pass
