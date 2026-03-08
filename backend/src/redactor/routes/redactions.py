import asyncio
import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from redactor.routes.jobs import _jobs
from redactor.models import JobStatus, RedactionRect, Suggestion
from redactor.pdf.processor import PDFProcessor
from redactor.storage.blob import BlobStorageClient
from redactor.config import get_settings

router = APIRouter()


class ApprovalUpdate(BaseModel):
    approved: bool


class ManualRedaction(BaseModel):
    page_num: int
    rects: list[RedactionRect]


def _get_job_or_404(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_blob(request: Request) -> BlobStorageClient:
    return request.app.state.blob_client


@router.post("/apply")
async def apply_redactions(job_id: str, request: Request):
    job = _get_job_or_404(job_id)
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
def add_manual_redaction(job_id: str, redaction: ManualRedaction):
    job = _get_job_or_404(job_id)
    s = Suggestion(
        id=str(uuid.uuid4()), text="[Manual]", category="Manual",
        reasoning="User-drawn redaction", context="",
        page_num=redaction.page_num, rects=redaction.rects,
        approved=True, source="manual"
    )
    job.suggestions.append(s)
    return s


@router.patch("/{suggestion_id}")
def toggle_approval(job_id: str, suggestion_id: str, update: ApprovalUpdate):
    job = _get_job_or_404(job_id)
    for s in job.suggestions:
        if s.id == suggestion_id:
            s.approved = update.approved
            return {"id": suggestion_id, "approved": update.approved}
    raise HTTPException(status_code=404, detail="Suggestion not found")
