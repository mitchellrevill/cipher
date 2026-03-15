import logging
from datetime import datetime
from typing import Optional

from redactor.models import Job, JobStatus

logger = logging.getLogger(__name__)


class JobService:
    """CRUD for job documents in a single Cosmos container."""

    def __init__(self, cosmos_container, blob_client=None):
        self.cosmos_container = cosmos_container
        self.blob_client = blob_client

    async def create_job(
        self,
        job_id: str,
        filename: str,
        user_id: Optional[str] = None,
        instructions: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Job:
        now = datetime.utcnow()
        job_doc = {
            "id": job_id,
            "job_id": job_id,
            "filename": filename,
            "status": JobStatus.PENDING.value,
            "page_count": 0,
            "error": None,
            "created_at": now.isoformat(),
            "completed_at": None,
            "user_id": user_id,
            "instructions": instructions or "",
            "workspace_id": workspace_id,
            "blob_path": f"jobs/{job_id}/original.pdf",
            "output_blob_path": f"jobs/{job_id}/redacted.pdf",
        }

        result = self.cosmos_container.create_item(body=job_doc)
        return self._doc_to_job(result)

    async def get_job(self, job_id: str) -> Optional[Job]:
        try:
            result = self.cosmos_container.read_item(item=job_id, partition_key=job_id)
            job = self._doc_to_job(result)
            logger.info("Retrieved job %s from Cosmos: status=%s", job_id, job.status)

            if self.blob_client:
                try:
                    suggestions = await self.blob_client.load_suggestions(job_id)
                    job.suggestions = suggestions
                except Exception as e:
                    logger.warning("Failed to load suggestions for %s: %s", job_id, e)

            return job
        except Exception:
            return None

    async def list_jobs(
        self,
        skip: int = 0,
        limit: int = 50,
        unassigned_only: bool = False,
        user_id: Optional[str] = None,
    ) -> list[Job]:
        filters: list[str] = []
        if user_id:
            filters.append(f"c.user_id = '{user_id}'")
        if unassigned_only:
            filters.append("(NOT IS_DEFINED(c.workspace_id) OR IS_NULL(c.workspace_id) OR c.workspace_id = '')")

        where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
        query = f"SELECT * FROM c{where_clause} ORDER BY c.created_at DESC OFFSET {skip} LIMIT {limit}"

        results = self.cosmos_container.query_items(
            query=query,
            enable_cross_partition_query=True,
        )
        if results is None:
            return []
        return [self._doc_to_job(doc) for doc in results]

    async def update_status(self, job_id: str, status: JobStatus, error: Optional[str] = None):
        doc = self.cosmos_container.read_item(item=job_id, partition_key=job_id)
        updates = {
            "status": status.value,
            "error": error,
        }

        if status == JobStatus.COMPLETE:
            updates["completed_at"] = datetime.utcnow().isoformat()

        doc.update(updates)
        self.cosmos_container.replace_item(item=job_id, body=doc)

    async def update_workspace_id(self, job_id: str, workspace_id: Optional[str]) -> None:
        doc = self.cosmos_container.read_item(item=job_id, partition_key=job_id)
        doc["workspace_id"] = workspace_id
        self.cosmos_container.replace_item(item=job_id, body=doc)

    async def list_jobs_by_ids(self, job_ids: list[str]) -> list[Job]:
        if not job_ids:
            return []
        placeholders = ", ".join(f"'{jid}'" for jid in job_ids)
        query = f"SELECT * FROM c WHERE c.job_id IN ({placeholders})"
        results = self.cosmos_container.query_items(
            query=query,
            enable_cross_partition_query=True,
        )
        if results is None:
            return []
        return [self._doc_to_job(doc) for doc in results]

    async def delete_job(self, job_id: str):
        await self.update_status(job_id, JobStatus.FAILED, "Archived")

    def _doc_to_job(self, doc: dict) -> Job:
        created_at = doc.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        completed_at = doc.get("completed_at")
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at)

        return Job(
            job_id=doc.get("job_id"),
            filename=doc.get("filename"),
            status=JobStatus(doc.get("status", "pending")),
            page_count=doc.get("page_count", 0),
            error=doc.get("error"),
            created_at=created_at,
            completed_at=completed_at,
            user_id=doc.get("user_id"),
            instructions=doc.get("instructions"),
            workspace_id=doc.get("workspace_id"),
            blob_path=doc.get("blob_path"),
            output_blob_path=doc.get("output_blob_path"),
        )
