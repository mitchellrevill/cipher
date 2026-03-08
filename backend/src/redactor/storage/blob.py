import json
import re
from azure.storage.blob.aio import BlobServiceClient
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError
from redactor.models import Suggestion

_JOB_ID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


class BlobStorageClient:
    def __init__(self, account_url: str, container: str):
        self._service = BlobServiceClient(
            account_url=account_url,
            credential=DefaultAzureCredential()
        )
        self._container_client = self._service.get_container_client(container)

    def _blob_name(self, job_id: str, filename: str) -> str:
        if not _JOB_ID_PATTERN.match(job_id):
            raise ValueError(f"Invalid job_id format: {job_id!r}")
        return f"jobs/{job_id}/{filename}"

    async def upload_pdf(self, job_id: str, data: bytes) -> str:
        name = self._blob_name(job_id, "original.pdf")
        blob = self._container_client.get_blob_client(name)
        await blob.upload_blob(data, overwrite=True)
        return name

    async def save_suggestions(self, job_id: str, suggestions: list[Suggestion]) -> None:
        name = self._blob_name(job_id, "suggestions.json")
        blob = self._container_client.get_blob_client(name)
        payload = json.dumps([s.model_dump() for s in suggestions])
        await blob.upload_blob(payload.encode(), overwrite=True)

    async def load_suggestions(self, job_id: str) -> list[Suggestion]:
        name = self._blob_name(job_id, "suggestions.json")
        blob = self._container_client.get_blob_client(name)
        try:
            stream = await blob.download_blob()
            data = await stream.readall()
            return [Suggestion(**s) for s in json.loads(data)]
        except ResourceNotFoundError:
            return []

    async def save_redacted_pdf(self, job_id: str, data: bytes) -> None:
        name = self._blob_name(job_id, "redacted.pdf")
        blob = self._container_client.get_blob_client(name)
        await blob.upload_blob(data, overwrite=True)

    async def download_original_pdf(self, job_id: str) -> bytes:
        name = self._blob_name(job_id, "original.pdf")
        blob = self._container_client.get_blob_client(name)
        stream = await blob.download_blob()
        return await stream.readall()

    async def download_redacted_pdf(self, job_id: str) -> bytes | None:
        name = self._blob_name(job_id, "redacted.pdf")
        blob = self._container_client.get_blob_client(name)
        try:
            stream = await blob.download_blob()
            return await stream.readall()
        except ResourceNotFoundError:
            return None
