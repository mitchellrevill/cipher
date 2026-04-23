import asyncio
import uuid
from typing import Annotated
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from app.auth import CurrentUser, get_current_user
from app.models import JobStatus, RedactionRect, Suggestion
from app.pdf.processor import PDFProcessor
from app.storage.blob import BlobStorageClient, get_blob_storage
from app.config import get_settings
from app.services.redaction_service import RedactionService
from app.services.job_service import JobService

router = APIRouter(dependencies=[Depends(get_current_user)])


class ApprovalUpdate(BaseModel):
    approved: bool


class ManualRedaction(BaseModel):
    page_num: int
    rects: list[RedactionRect]


class BulkApprovalResponse(BaseModel):
    approved: bool
    updated_count: int


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


async def _require_owned_job(job_id: str, job_service: JobService, current_user: CurrentUser):
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return job


@router.post("/apply")
async def apply_redactions(
    job_id: str,
    request: Request,
    job_service: Annotated[JobService, Depends(get_job_service)],
    current_user: CurrentUser = Depends(get_current_user),
):
    """Apply redactions by saving approved suggestions and generating redacted PDF."""
    job = await _require_owned_job(job_id, job_service, current_user)
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
    redaction_service: Annotated[RedactionService, Depends(get_redaction_service)],
    current_user: CurrentUser = Depends(get_current_user),
):
    """Add a manually created redaction suggestion."""
    from datetime import datetime
    job = await _require_owned_job(job_id, job_service, current_user)
    s = Suggestion(
        id=str(uuid.uuid4()), job_id=job_id, text="[Manual]", category="Manual",
        reasoning="User-drawn redaction", context="",
        page_num=redaction.page_num, rects=redaction.rects,
        approved=True, source="manual", created_at=datetime.utcnow()
    )
    job.suggestions.append(s)
    # Persist manual suggestion to blob storage.
    await redaction_service.add_manual_suggestion(job_id, s)
    return s


@router.patch("/{suggestion_id}")
async def toggle_approval(
    job_id: str,
    suggestion_id: str,
    update: ApprovalUpdate,
    job_service: Annotated[JobService, Depends(get_job_service)],
    redaction_service: Annotated[RedactionService, Depends(get_redaction_service)],
    current_user: CurrentUser = Depends(get_current_user),
):
    """Toggle approval status for a suggestion."""
    job = await _require_owned_job(job_id, job_service, current_user)
    for s in job.suggestions:
        if s.id == suggestion_id:
            s.approved = update.approved
            # Persist approval change to blob storage.
            await redaction_service.toggle_approval(job_id, suggestion_id, update.approved)
            return {"id": suggestion_id, "approved": update.approved}
    raise HTTPException(status_code=404, detail="Suggestion not found")


@router.post("/approve-all", response_model=BulkApprovalResponse)
async def approve_all_suggestions(
    job_id: str,
    job_service: Annotated[JobService, Depends(get_job_service)],
    redaction_service: Annotated[RedactionService, Depends(get_redaction_service)],
    current_user: CurrentUser = Depends(get_current_user),
):
    """Approve all unapproved suggestions for a job in a single storage update."""
    job = await _require_owned_job(job_id, job_service, current_user)

    updated_count = 0
    updated_at = None
    from datetime import datetime
    for suggestion in job.suggestions:
        if suggestion.approved:
            continue

        if updated_at is None:
            updated_at = datetime.utcnow()

        suggestion.approved = True
        suggestion.updated_at = updated_at
        updated_count += 1

    persisted_count = await redaction_service.bulk_update_approvals(job_id, True)

    return {
        "approved": True,
        "updated_count": max(updated_count, persisted_count),
    }
