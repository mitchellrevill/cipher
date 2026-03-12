"""
Job service for document processing lifecycle management.

Manages creation, retrieval, and state management of document processing jobs.
Persists job data to Cosmos DB with indefinite retention for UX.
"""

import logging
from typing import Optional, List
from datetime import datetime
from redactor.models import Job, JobStatus

logger = logging.getLogger(__name__)


class JobService:
    """
    Job lifecycle management service.

    Handles CRUD operations for jobs and state persistence.
    Integrates with Cosmos DB for indefinite job history.
    """

    CONTAINER_NAME = "jobs"
    PARTITION_KEY = "job_id"

    def __init__(self, cosmos_client, blob_client=None):
        """Initialize JobService with Cosmos DB and optional Blob Storage clients."""
        self.cosmos_client = cosmos_client
        self.blob_client = blob_client
        self.container = None

    async def _get_container(self):
        """Lazy-load container reference."""
        if self.container is None:
            # Will be set up when DB is initialized (Task 9)
            pass
        return self.container

    async def create_job(self, job_id: str, filename: str, user_id: Optional[str] = None) -> Job:
        """
        Create a new job.

        Args:
            job_id: Unique job identifier (UUID)
            filename: Original filename
            user_id: Optional user identifier

        Returns:
            Job: Created job with metadata
        """
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
            "suggestions_count": 0
        }

        # Create item in Cosmos DB
        result = self.cosmos_client.create_item(body=job_doc)

        return self._doc_to_job(result)

    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job if found, None otherwise
        """
        try:
            result = self.cosmos_client.read_item(item=job_id, partition_key=job_id)
            job = self._doc_to_job(result)
            logger.info(f"Retrieved job {job_id} from Cosmos: status={job.status}, suggestions_count={job.suggestions_count}")

            # Load suggestions from blob storage if available
            if self.blob_client:
                logger.info(f"blob_client is available, attempting to load suggestions for {job_id}")
                try:
                    suggestions = await self.blob_client.load_suggestions(job_id)
                    job.suggestions = suggestions
                    logger.info(f"Loaded {len(suggestions)} suggestions for job {job_id}")
                except Exception as e:
                    logger.warning(f"Failed to load suggestions for {job_id}: {type(e).__name__}: {str(e)[:100]}")
            else:
                logger.warning(f"blob_client is None for job {job_id} - suggestions will not be loaded")

            return job
        except Exception:
            return None

    async def list_jobs(self, skip: int = 0, limit: int = 10) -> List[Job]:
        """
        List jobs with pagination.

        Args:
            skip: Number of items to skip
            limit: Maximum items to return

        Returns:
            List of jobs
        """
        # Placeholder for Cosmos DB query
        # Will be implemented when container is available (Task 9)
        return []

    async def update_status(self, job_id: str, status: JobStatus, error: Optional[str] = None):
        """
        Update job status.

        Args:
            job_id: Job identifier
            status: New status
            error: Optional error message
        """
        updates = {
            "status": status.value,
            "error": error
        }

        if status == JobStatus.COMPLETE:
            updates["completed_at"] = datetime.utcnow().isoformat()

        self.cosmos_client.update_item(item=job_id, body=updates)

    async def update_suggestions(self, job_id: str, suggestions_count: int):
        """
        Update suggestion count for a job.

        Args:
            job_id: Job identifier
            suggestions_count: Number of suggestions
        """
        self.cosmos_client.update_item(
            item=job_id,
            body={"suggestions_count": suggestions_count}
        )

    async def delete_job(self, job_id: str):
        """
        Soft delete a job (mark as archived).

        Args:
            job_id: Job identifier
        """
        # Soft delete by marking status
        await self.update_status(job_id, JobStatus.FAILED, "Archived")

    def _doc_to_job(self, doc: dict) -> Job:
        """Convert Cosmos DB document to Job model."""
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
            suggestions_count=doc.get("suggestions_count", 0)
        )
