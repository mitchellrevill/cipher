import asyncio
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from redactor.config import get_settings
from redactor.models import Job, JobStatus
from redactor.storage.blob import BlobStorageClient
from redactor.pipeline.orchestrator import run_pipeline

router = APIRouter()
_jobs: dict[str, Job] = {}  # in-memory; replace with DB in production


def _blob_client():
    s = get_settings()
    return BlobStorageClient(s.azure_storage_account_url, s.azure_storage_container)


async def _run_job(job_id: str, pdf_bytes: bytes, instructions: str):
    _jobs[job_id].status = JobStatus.PROCESSING
    try:
        settings = get_settings()
        suggestions = await run_pipeline(pdf_bytes, instructions, settings)
        _jobs[job_id].suggestions = suggestions
        _jobs[job_id].status = JobStatus.COMPLETE
        blob = _blob_client()
        await blob.save_suggestions(job_id, suggestions)
    except Exception as ex:
        _jobs[job_id].status = JobStatus.FAILED
        _jobs[job_id].error = str(ex)


@router.post("", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    instructions: str = Form(default="")
):
    job_id = str(uuid.uuid4())
    pdf_bytes = await file.read()
    blob = _blob_client()
    await blob.upload_pdf(job_id, pdf_bytes)
    _jobs[job_id] = Job(job_id=job_id, status=JobStatus.PENDING)
    background_tasks.add_task(_run_job, job_id, pdf_bytes, instructions)
    return {"job_id": job_id}


@router.get("/{job_id}")
async def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/stream")
async def stream_job_status(job_id: str):
    """SSE endpoint — streams status updates until job completes."""
    from sse_starlette.sse import EventSourceResponse

    async def event_generator():
        while True:
            job = _jobs.get(job_id)
            if not job:
                yield {"data": '{"error": "not found"}'}
                break
            yield {"data": job.model_dump_json()}
            if job.status in (JobStatus.COMPLETE, JobStatus.FAILED):
                break
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.get("/{job_id}/download")
async def download_redacted(job_id: str):
    blob = _blob_client()
    try:
        pdf_bytes = await blob.download_redacted_pdf(job_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Redacted PDF not found")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{job_id}_redacted.pdf"'}
    )
