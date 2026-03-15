from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from redactor.services.job_service import JobService
from redactor.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)

router = APIRouter()
DEFAULT_USER_ID = "user_default"


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class AddDocumentRequest(BaseModel):
    document_id: str = Field(min_length=1)


class CreateRuleRequest(BaseModel):
    pattern: str = Field(min_length=1)
    category: str = Field(min_length=1)
    confidence_threshold: float = 0.8
    applies_to: list[str] | None = None


class ExcludeDocumentRequest(BaseModel):
    document_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


async def get_workspace_service(request: Request) -> WorkspaceService:
    return request.app.container.services.workspace_service()


async def get_job_service(request: Request) -> JobService:
    return request.app.container.services.job_service()


@router.post("", status_code=201)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
):
    return await service.create_workspace(
        user_id=DEFAULT_USER_ID,
        name=payload.name,
        description=payload.description,
    )


@router.get("")
async def list_workspaces(
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
):
    return await service.list_workspaces(DEFAULT_USER_ID)


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
):
    workspace = await service.get_workspace_state(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

# Enrich each document entry with job metadata (filename, status, etc.)
    doc_ids = [doc["id"] for doc in workspace.get("documents", [])]
    if doc_ids:
        try:
            jobs = await job_service.list_jobs_by_ids(doc_ids)
            jobs_by_id = {job.job_id: job for job in jobs}
            for doc in workspace["documents"]:
                job = jobs_by_id.get(doc["id"])
                if job:
                    doc["filename"] = job.filename
                    doc["status"] = job.status.value if job.status else None
                    doc["page_count"] = job.page_count
                    doc["suggestions_count"] = job.suggestions_count
        except Exception as exc:
            logger.warning("Failed to enrich workspace documents with job metadata: %s", exc)

    return workspace

@router.post("/{workspace_id}/documents")
async def add_document_to_workspace(
    workspace_id: str,
    payload: AddDocumentRequest,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
):
    try:
        result = await service.add_document(workspace_id, payload.document_id)
        try:
            await job_service.update_workspace_id(payload.document_id, workspace_id)
        except Exception as exc:
            logger.warning("Failed to update workspace_id on job %s: %s", payload.document_id, exc)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{workspace_id}/documents/{document_id}")
async def remove_document_from_workspace(
    workspace_id: str,
    document_id: str,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
):
    try:
        result = await service.remove_document(workspace_id, document_id)
        try:
            await job_service.update_workspace_id(document_id, None)
        except Exception as exc:
            logger.warning("Failed to clear workspace_id on job %s: %s", document_id, exc)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{workspace_id}/rules", status_code=201)
async def create_workspace_rule(
    workspace_id: str,
    payload: CreateRuleRequest,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
):
    try:
        return await service.create_rule(
            workspace_id=workspace_id,
            pattern=payload.pattern,
            category=payload.category,
            confidence_threshold=payload.confidence_threshold,
            applies_to=payload.applies_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{workspace_id}/exclusions", status_code=201)
async def exclude_document(
    workspace_id: str,
    payload: ExcludeDocumentRequest,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
):
    try:
        return await service.exclude_document(workspace_id, payload.document_id, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{workspace_id}/exclusions/{exclusion_id}")
async def remove_exclusion(
    workspace_id: str,
    exclusion_id: str,
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
):
    try:
        return await service.remove_exclusion(workspace_id, exclusion_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
