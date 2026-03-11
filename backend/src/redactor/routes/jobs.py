import asyncio
import uuid
from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import StreamingResponse
from redactor.config import get_settings
from redactor.models import Job, JobStatus
from redactor.services.job_service import JobService
from redactor.storage.blob import BlobStorageClient, get_blob_storage
from redactor.pipeline.orchestrator import run_pipeline

router = APIRouter()

MAX_STREAM_SECONDS = 600  # 10 minutes


def _get_blob(request: Request) -> BlobStorageClient:
    """Get BlobStorageClient from app container."""
    settings = get_settings()
    return get_blob_storage(
        settings.azure_storage_account_url,
        settings.azure_storage_container,
        account_key=settings.azure_storage_account_key or None,
    )


async def get_job_service(request: Request) -> JobService:
    """Get JobService from app container via dependency injection."""
    # Services live under the `services` subcontainer on AppContainer
    return request.app.container.services.job_service()


async def _run_job(
    job_id: str,
    pdf_bytes: bytes,
    instructions: str,
    blob: BlobStorageClient,
    job_service: JobService
):
    """Run redaction pipeline and update job status."""
    await job_service.update_status(job_id, JobStatus.PROCESSING)
    try:
        settings = get_settings()
        suggestions = await run_pipeline(pdf_bytes, instructions, settings)
        await job_service.update_suggestions(job_id, len(suggestions))
        await blob.save_suggestions(job_id, suggestions)
        await job_service.update_status(job_id, JobStatus.COMPLETE)
    except Exception as ex:
        await job_service.update_status(job_id, JobStatus.FAILED, str(ex))


@router.post("", status_code=202)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    instructions: str = Form(default=""),
    job_service: Annotated[JobService, Depends(get_job_service)] = None
):
    """Upload a document for redaction."""
    job_id = str(uuid.uuid4())
    pdf_bytes = await file.read()

    # Create job via service
    job = await job_service.create_job(job_id=job_id, filename=file.filename)

    # Upload PDF to blob storage
    blob = _get_blob(request)
    await blob.upload_pdf(job_id, pdf_bytes)

    # Start pipeline in background
    background_tasks.add_task(_run_job, job_id, pdf_bytes, instructions, blob, job_service)

    return {"job_id": job.job_id}


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    job_service: Annotated[JobService, Depends(get_job_service)] = None
):
    """Get job status."""
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/stream")
async def stream_job_status(
    job_id: str,
    job_service: Annotated[JobService, Depends(get_job_service)] = None
):
    """SSE endpoint — streams status updates until job completes."""
    from sse_starlette.sse import EventSourceResponse

    async def event_generator():
        elapsed = 0
        while elapsed < MAX_STREAM_SECONDS:
            job = await job_service.get_job(job_id)
            if not job:
                yield {"data": '{"error": "not found"}'}
                break
            yield {"data": job.model_dump_json()}
            if job.status in (JobStatus.COMPLETE, JobStatus.FAILED):
                break
            await asyncio.sleep(1)
            elapsed += 1
        else:
            # Timeout — mark job as failed if still processing
            job = await job_service.get_job(job_id)
            if job and job.status == JobStatus.PROCESSING:
                await job_service.update_status(job_id, JobStatus.FAILED, "Processing timeout")

    return EventSourceResponse(event_generator())


@router.get("/{job_id}/download")
async def download_redacted(job_id: str, request: Request):
    """Download redacted PDF."""
    blob = _get_blob(request)
    try:
        pdf_bytes = await blob.download_redacted_pdf(job_id)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    except Exception:
        raise HTTPException(status_code=404, detail="Redacted PDF not found")
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Redacted PDF not found")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{job_id}_redacted.pdf"'}
    )
