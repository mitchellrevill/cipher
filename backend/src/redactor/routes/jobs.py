import asyncio
import uuid
import json
import logging
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import StreamingResponse
from redactor.config import get_settings
from redactor.models import Job, JobStatus, PageStatusEvent, SuggestionFoundEvent
from redactor.services.job_service import JobService
from redactor.services.workspace_service import WorkspaceService
from redactor.storage.blob import BlobStorageClient, get_blob_storage
from redactor.pipeline.orchestrator import run_pipeline

logger = logging.getLogger(__name__)


def _validate_job_id(job_id: str) -> bool:
    """Validate that job_id is a valid UUID."""
    try:
        UUID(job_id)
        return True
    except ValueError:
        return False

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


async def get_workspace_service(request: Request) -> WorkspaceService:
    return request.app.container.services.workspace_service()


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
    workspace_id: str = Form(default=""),
    job_service: Annotated[JobService, Depends(get_job_service)] = None,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)] = None,
):
    """Upload a document for redaction."""
    job_id = str(uuid.uuid4())
    pdf_bytes = await file.read()

    # Create job via service
    normalized_workspace_id = workspace_id or None
    job = await job_service.create_job(
        job_id=job_id,
        filename=file.filename,
        instructions=instructions,
        workspace_id=normalized_workspace_id,
    )

    if normalized_workspace_id:
        try:
            await workspace_service.add_document(normalized_workspace_id, job_id)
        except Exception as exc:
            logger.warning("Failed to add uploaded document %s to workspace %s: %s", job_id, normalized_workspace_id, exc)

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
        # Validate job_id format
        if not _validate_job_id(job_id):
            yield {"data": json.dumps({"error": "Invalid job ID format"})}
            return

        elapsed = 0
        while elapsed < MAX_STREAM_SECONDS:
            try:
                job = await job_service.get_job(job_id)
            except Exception as e:
                logger.exception(f"Error retrieving job {job_id}")
                yield {"data": json.dumps({"error": f"Failed to retrieve job: {str(e)}"})}
                return

            if not job:
                yield {"data": json.dumps({"error": "not found"})}
                break
            yield {"data": job.model_dump_json()}
            if job.status in (JobStatus.COMPLETE, JobStatus.FAILED):
                break
            await asyncio.sleep(1)
            elapsed += 1
        else:
            # Timeout — mark job as failed if still processing
            try:
                job = await job_service.get_job(job_id)
                if job and job.status == JobStatus.PROCESSING:
                    await job_service.update_status(job_id, JobStatus.FAILED, "Processing timeout")
            except Exception as e:
                logger.exception(f"Error updating job status on timeout for {job_id}")

    return EventSourceResponse(event_generator())


@router.get("/{job_id}/stream-analysis")
async def stream_analysis(
    job_id: str,
    request: Request,
    job_service: Annotated[JobService, Depends(get_job_service)] = None
):
    """
    SSE endpoint for streaming redaction analysis.
    Returns page_status and suggestion_found events as they occur.
    """
    settings = get_settings()
    blob = _get_blob(request)

    async def event_generator():
        # Validate job_id format
        if not _validate_job_id(job_id):
            yield f"event: error\ndata: {json.dumps({'error': 'Invalid job ID format'})}\n\n"
            return

        # Initialize clients to None for proper cleanup
        doc_client = None
        oai_client = None
        pii_client = None

        try:
            # Get job and PDF
            job = await job_service.get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                return

            pdf_bytes = await blob.download_pdf(job_id)
            if not pdf_bytes:
                yield f"data: {json.dumps({'error': 'PDF not found'})}\n\n"
                return

            # Create clients
            from redactor.pipeline.doc_intelligence import DocIntelligenceClient
            from redactor.pipeline.pii_service import PIIServiceClient
            from redactor.pipeline.openai_client import OpenAIRedactionClient
            from redactor.pipeline.page_processor import StreamingPageProcessor

            doc_client = DocIntelligenceClient(
                settings.azure_doc_intel_endpoint,
                settings.azure_doc_intel_key
            )
            oai_client = OpenAIRedactionClient(
                settings.azure_openai_endpoint,
                settings.azure_openai_key,
                settings.azure_openai_deployment,
                settings.azure_openai_api_version
            )
            pii_client = PIIServiceClient(
                settings.azure_language_endpoint,
                settings.azure_language_key
            ) if settings.enable_pii_service else None

            # Analyze document
            logger.info(f"Stream analysis started for job {job_id}")
            analysis = await doc_client.analyse(pdf_bytes)

            # Parse instructions
            parsed_instructions = await oai_client.parse_instructions(
                job.instructions or ""
            )
            pii_exceptions = {e.lower() for e in parsed_instructions.get("exceptions", [])}
            sensitive_rule = parsed_instructions.get("sensitive_content_rules")

            # Create processor and stream events
            processor = StreamingPageProcessor(
                analysis=analysis,
                pii_client=pii_client,
                oai_client=oai_client,
                config=settings,
                batch_size=4,
            )

            async for event in processor.process_pages_streaming(
                pii_exceptions=pii_exceptions,
                sensitive_rule=sensitive_rule,
            ):
                # Serialize event to JSON
                if isinstance(event, PageStatusEvent):
                    event_type = "page_status"
                    data = event.model_dump()
                elif isinstance(event, SuggestionFoundEvent):
                    event_type = "suggestion_found"
                    data = event.model_dump()
                else:
                    continue

                # Send as SSE
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(data)}\n\n"

            # Send completion event
            yield f"event: analysis_complete\n"
            yield f"data: {json.dumps({'status': 'complete'})}\n\n"

        except Exception as e:
            logger.exception("Stream analysis error")
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        finally:
            # Resource cleanup for Azure clients
            # Note: Azure SDK clients use reference counting and garbage collection.
            # Explicit closing is optional but can be added if clients support it.
            # If clients have close() or __aexit__ methods, they will be garbage collected.
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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


@router.get("/{job_id}/download-original")
async def download_original(job_id: str, request: Request):
    """Download original uploaded PDF."""
    blob = _get_blob(request)
    try:
        pdf_bytes = await blob.download_original_pdf(job_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Original PDF not found")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{job_id}_original.pdf"'}
    )
