import asyncio
import uuid
from typing import Annotated
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from redactor.models import JobStatus, RedactionRect, Suggestion
from redactor.pdf.processor import PDFProcessor
from redactor.storage.blob import BlobStorageClient, get_blob_storage
from redactor.config import get_settings
from redactor.services.redaction_service import RedactionService
from redactor.services.job_service import JobService

router = APIRouter()


class ApprovalUpdate(BaseModel):
    approved: bool


class ManualRedaction(BaseModel):
    page_num: int
    rects: list[RedactionRect]


def _get_blob(request: Request) -> BlobStorageClient:
    settings = get_settings()
    return get_blob_storage(
        settings.azure_storage_account_url,
        settings.azure_storage_container,
        account_key=settings.azure_storage_account_key or None,
    )


async def get_job_service(request: Request) -> JobService:
    """Get JobService from app container via dependency injection."""
    return request.app.container.services.job_service()


async def get_redaction_service(request: Request) -> RedactionService:
    """Get RedactionService from app container via dependency injection."""
    return request.app.container.services.redaction_service()


@router.post("/apply")
async def apply_redactions(
    job_id: str,
    request: Request,
    job_service: Annotated[JobService, Depends(get_job_service)],
    redaction_service: Annotated[RedactionService, Depends(get_redaction_service)]
):
    """Apply redactions by saving approved suggestions and generating redacted PDF."""
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="Job not complete")

    blob = _get_blob(request)
    try:
        pdf_bytes = await blob.download_original_pdf(job_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Original PDF not found in storage")

    approved = [s for s in job.suggestions if s.approved]
    rects_by_page: dict[int, list[RedactionRect]] = {}
    for suggestion in approved:
        rects_by_page.setdefault(suggestion.page_num, []).extend(suggestion.rects)

    processor = PDFProcessor(pdf_bytes)
    try:
        redacted_bytes = await asyncio.to_thread(processor.apply_redactions, rects_by_page)
        await blob.save_redacted_pdf(job_id, redacted_bytes)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to apply redactions: {ex}")

    return {"status": "applied", "redaction_count": len(approved)}


@router.post("/manual")
async def add_manual_redaction(
    job_id: str,
    redaction: ManualRedaction,
    job_service: Annotated[JobService, Depends(get_job_service)],
    redaction_service: Annotated[RedactionService, Depends(get_redaction_service)]
):
    """Add a manually created redaction suggestion."""
    from datetime import datetime
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    s = Suggestion(
        id=str(uuid.uuid4()), job_id=job_id, text="[Manual]", category="Manual",
        reasoning="User-drawn redaction", context="",
        page_num=redaction.page_num, rects=redaction.rects,
        approved=True, source="manual", created_at=datetime.utcnow()
    )
    job.suggestions.append(s)
    # Persist manual suggestion to database
    await redaction_service.add_manual_suggestion(job_id, s)
    return s


@router.patch("/{suggestion_id}")
async def toggle_approval(
    job_id: str,
    suggestion_id: str,
    update: ApprovalUpdate,
    job_service: Annotated[JobService, Depends(get_job_service)],
    redaction_service: Annotated[RedactionService, Depends(get_redaction_service)]
):
    """Toggle approval status for a suggestion."""
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for s in job.suggestions:
        if s.id == suggestion_id:
            s.approved = update.approved
            # Persist approval change to database
            await redaction_service.toggle_approval(job_id, suggestion_id, update.approved)
            return {"id": suggestion_id, "approved": update.approved}
    raise HTTPException(status_code=404, detail="Suggestion not found")
