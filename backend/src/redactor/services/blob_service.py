from typing import Optional
from azure.storage.blob import BlobServiceClient

class BlobService:
    """
    Azure Blob Storage service for PDF lifecycle management.

    Handles upload, download, and deletion of PDF files.
    """

    def __init__(self, blob_client: BlobServiceClient):
        """Initialize BlobService with Azure Blob Storage client."""
        self.blob_client = blob_client
