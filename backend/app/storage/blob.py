import json
import re
from azure.storage.blob.aio import BlobServiceClient
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError
from backend.app.models import Suggestion

_inmemory_blob_instance = None

_JOB_ID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


class BlobStorageClient:
    def __init__(self, account_url: str, container: str, account_key: str | None = None):
        if account_key:
            # Build connection string for key-based auth
            account_name = account_url.rstrip("/").split("//")[1].split(".")[0]
            connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
            self._service = BlobServiceClient.from_connection_string(connection_string)
        else:
            # Use managed identity / DefaultAzureCredential
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
        payload = json.dumps([s.model_dump(mode='json') for s in suggestions])
        await blob.upload_blob(payload.encode(), overwrite=True)

    async def upload_json(self, blob_name: str, data: list | dict) -> None:
        blob = self._container_client.get_blob_client(blob_name)
        payload = json.dumps(data)
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

    async def download_json(self, blob_name: str) -> list | dict | None:
        blob = self._container_client.get_blob_client(blob_name)
        try:
            stream = await blob.download_blob()
            data = await stream.readall()
            return json.loads(data)
        except ResourceNotFoundError:
            return None

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


class InMemoryBlobStorageClient:
    """Simple in-memory blob client for local development and testing.

    Stores blobs in a dict keyed by blob name. Implements the same
    async interface used by the app (`upload_pdf`, `save_suggestions`,
    `download_original_pdf`, `download_redacted_pdf`, etc.).
    """
    def __init__(self):
        self._store: dict[str, bytes] = {}

    def _blob_name(self, job_id: str, filename: str) -> str:
        return f"jobs/{job_id}/{filename}"

    async def upload_pdf(self, job_id: str, data: bytes) -> str:
        name = self._blob_name(job_id, "original.pdf")
        self._store[name] = data
        return name

    async def save_suggestions(self, job_id: str, suggestions: list[Suggestion]) -> None:
        name = self._blob_name(job_id, "suggestions.json")
        payload = json.dumps([s.model_dump(mode='json') for s in suggestions])
        self._store[name] = payload.encode()

    async def upload_json(self, blob_name: str, data: list | dict) -> None:
        self._store[blob_name] = json.dumps(data).encode()

    async def load_suggestions(self, job_id: str) -> list[Suggestion]:
        name = self._blob_name(job_id, "suggestions.json")
        data = self._store.get(name)
        if not data:
            return []
        return [Suggestion(**s) for s in json.loads(data)]

    async def download_json(self, blob_name: str) -> list | dict | None:
        data = self._store.get(blob_name)
        if data is None:
            return None
        return json.loads(data)

    async def save_redacted_pdf(self, job_id: str, data: bytes) -> None:
        name = self._blob_name(job_id, "redacted.pdf")
        self._store[name] = data

    async def download_original_pdf(self, job_id: str) -> bytes:
        name = self._blob_name(job_id, "original.pdf")
        data = self._store.get(name)
        if data is None:
            raise ValueError("Original PDF not found")
        return data

    async def download_redacted_pdf(self, job_id: str) -> bytes | None:
        name = self._blob_name(job_id, "redacted.pdf")
        return self._store.get(name)


def get_blob_storage(
    account_url: str,
    container: str,
    account_key: str | None = None,
) -> BlobStorageClient | InMemoryBlobStorageClient:
    """Create the configured blob client or fall back to a shared in-memory store.

    Auth priority:
    1. ``account_key`` (Storage Shared Key) when explicitly provided.
    2. ``DefaultAzureCredential`` (managed identity / az-login) otherwise.
    3. In-memory store when the account URL is unset (pure local dev).

    The in-memory fallback must be process-wide so upload/apply/download
    requests all see the same stored files during local development.
    """
    global _inmemory_blob_instance

    if not account_url:
        if _inmemory_blob_instance is None:
            _inmemory_blob_instance = InMemoryBlobStorageClient()
        return _inmemory_blob_instance

    return BlobStorageClient(account_url, container, account_key=account_key or None)
