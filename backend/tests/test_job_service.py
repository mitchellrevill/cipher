"""Tests for JobService."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from app.services.job_service import JobService
from app.models import JobStatus


def make_cosmos():
    cosmos = MagicMock()
    cosmos.create_item = MagicMock()
    cosmos.read_item = MagicMock()
    cosmos.replace_item = MagicMock()
    cosmos.query_items = MagicMock(return_value=[])
    return cosmos


def make_blob():
    blob = MagicMock()
    blob.load_suggestions = AsyncMock(return_value=[])
    return blob


@pytest.mark.asyncio
async def test_create_job_sets_blob_path():
    cosmos = make_cosmos()
    cosmos.create_item.return_value = {
        "id": "job-123",
        "job_id": "job-123",
        "filename": "test.pdf",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "page_count": 0,
        "error": None,
        "completed_at": None,
        "user_id": None,
        "workspace_id": None,
        "blob_path": "jobs/job-123/original.pdf",
        "output_blob_path": "jobs/job-123/redacted.pdf",
    }
    service = JobService(cosmos_container=cosmos, blob_client=make_blob())

    job = await service.create_job(job_id="job-123", filename="test.pdf")

    assert job.job_id == "job-123"
    assert job.blob_path == "jobs/job-123/original.pdf"
    assert job.output_blob_path == "jobs/job-123/redacted.pdf"
    call_body = cosmos.create_item.call_args.kwargs["body"]
    assert call_body["blob_path"] == "jobs/job-123/original.pdf"
    assert call_body["output_blob_path"] == "jobs/job-123/redacted.pdf"
    assert "suggestions_count" not in call_body


@pytest.mark.asyncio
async def test_create_job_with_workspace_id():
    cosmos = make_cosmos()
    cosmos.create_item.return_value = {
        "id": "job-abc",
        "job_id": "job-abc",
        "filename": "test.pdf",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "page_count": 0,
        "error": None,
        "completed_at": None,
        "user_id": None,
        "workspace_id": "ws_abc",
        "blob_path": "jobs/job-abc/original.pdf",
        "output_blob_path": "jobs/job-abc/redacted.pdf",
    }
    service = JobService(cosmos_container=cosmos, blob_client=make_blob())

    await service.create_job(job_id="job-abc", filename="test.pdf", workspace_id="ws_abc")

    assert cosmos.create_item.call_args.kwargs["body"]["workspace_id"] == "ws_abc"


@pytest.mark.asyncio
async def test_get_job_loads_suggestions_from_blob():
    cosmos = make_cosmos()
    cosmos.read_item.return_value = {
        "id": "job-3",
        "job_id": "job-3",
        "filename": "test.pdf",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "page_count": 0,
        "error": None,
        "completed_at": None,
        "user_id": None,
        "workspace_id": None,
        "blob_path": "jobs/job-3/original.pdf",
        "output_blob_path": "jobs/job-3/redacted.pdf",
    }
    blob = make_blob()
    service = JobService(cosmos_container=cosmos, blob_client=blob)

    job = await service.get_job(job_id="job-3")

    assert job is not None
    blob.load_suggestions.assert_called_once_with("job-3")


@pytest.mark.asyncio
async def test_get_job_returns_none_when_not_found():
    cosmos = make_cosmos()
    cosmos.read_item.side_effect = Exception("Not found")
    service = JobService(cosmos_container=cosmos, blob_client=make_blob())

    job = await service.get_job(job_id="nonexistent")

    assert job is None


@pytest.mark.asyncio
async def test_update_status_replaces_document():
    cosmos = make_cosmos()
    cosmos.read_item.return_value = {
        "id": "job-123",
        "job_id": "job-123",
        "filename": "test.pdf",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "blob_path": "jobs/job-123/original.pdf",
        "output_blob_path": "jobs/job-123/redacted.pdf",
    }
    service = JobService(cosmos_container=cosmos, blob_client=make_blob())

    await service.update_status(job_id="job-123", status=JobStatus.COMPLETE)

    cosmos.replace_item.assert_called_once()
    replaced_body = cosmos.replace_item.call_args.kwargs["body"]
    assert replaced_body["status"] == JobStatus.COMPLETE.value
    assert replaced_body["completed_at"]


@pytest.mark.asyncio
async def test_list_jobs_returns_all():
    cosmos = make_cosmos()
    cosmos.query_items.return_value = [
        {
            "id": "job-1",
            "job_id": "job-1",
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "blob_path": "jobs/job-1/original.pdf",
            "output_blob_path": "jobs/job-1/redacted.pdf",
        },
        {
            "id": "job-2",
            "job_id": "job-2",
            "status": "complete",
            "created_at": datetime.utcnow().isoformat(),
            "blob_path": "jobs/job-2/original.pdf",
            "output_blob_path": "jobs/job-2/redacted.pdf",
        },
    ]
    service = JobService(cosmos_container=cosmos, blob_client=make_blob())

    jobs = await service.list_jobs()

    assert len(jobs) == 2


@pytest.mark.asyncio
async def test_list_jobs_unassigned_only():
    cosmos = make_cosmos()
    service = JobService(cosmos_container=cosmos, blob_client=make_blob())

    await service.list_jobs(unassigned_only=True)

    query_text = cosmos.query_items.call_args.kwargs["query"]
    assert "workspace_id" in query_text
