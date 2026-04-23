import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agent.tools.suggestions import SuggestionTools
from app.models import RedactionRect, Suggestion


def make_suggestion(sid="s1", text="John Smith", category="PII", approved=False):
    return Suggestion(
        id=sid,
        job_id="job1",
        text=text,
        category=category,
        reasoning="PII",
        context="",
        page_num=0,
        rects=[RedactionRect(x0=0, y0=0, x1=1, y1=1)],
        approved=approved,
        source="ai",
        created_at=datetime.utcnow(),
    )


def make_job(suggestions=None):
    return SimpleNamespace(job_id="job1", filename="test.pdf", suggestions=suggestions or [make_suggestion()])


def make_services(job=None, found=True):
    job_service = AsyncMock()
    job_service.get_job.return_value = job or (make_job() if found else None)
    redaction_service = AsyncMock()
    redaction_service.toggle_approval = AsyncMock(return_value=None)
    redaction_service.delete_suggestion = AsyncMock(return_value=None)
    redaction_service.add_manual_suggestion = AsyncMock(return_value=None)
    return job_service, redaction_service


@pytest.mark.asyncio
async def test_approve_suggestion_returns_confirmation():
    job_service, redaction_service = make_services()
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    result = await tools.approve_suggestion(doc_id="job1", suggestion_id="s1", approved=True)

    data = json.loads(result)
    assert data["status"] == "updated"
    assert data["approved"] is True
    assert data["suggestion_id"] == "s1"


@pytest.mark.asyncio
async def test_approve_suggestion_returns_error_for_missing_job():
    job_service, redaction_service = make_services(found=False)
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    result = await tools.approve_suggestion(doc_id="missing", suggestion_id="s1", approved=True)

    assert result.startswith("Error:")
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_approve_suggestion_returns_error_for_missing_suggestion():
    job_service, redaction_service = make_services()
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    result = await tools.approve_suggestion(doc_id="job1", suggestion_id="no-such", approved=True)

    assert result.startswith("Error:")
    assert "suggestion not found" in result.lower()


@pytest.mark.asyncio
async def test_delete_suggestion_returns_confirmation():
    job_service, redaction_service = make_services()
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    result = await tools.delete_suggestion(doc_id="job1", suggestion_id="s1")

    data = json.loads(result)
    assert data["status"] == "deleted"
    assert data["suggestion_id"] == "s1"
    redaction_service.delete_suggestion.assert_awaited_once_with("job1", "s1")


@pytest.mark.asyncio
async def test_delete_suggestion_returns_error_for_missing_suggestion():
    job_service, redaction_service = make_services()
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    result = await tools.delete_suggestion(doc_id="job1", suggestion_id="no-such")

    assert result.startswith("Error:")
    assert "suggestion not found" in result.lower()


@pytest.mark.asyncio
async def test_delete_suggestion_returns_error_for_missing_job():
    job_service, redaction_service = make_services(found=False)
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    result = await tools.delete_suggestion(doc_id="missing", suggestion_id="s1")

    assert result.startswith("Error:")


@pytest.mark.asyncio
async def test_create_suggestion_returns_new_id():
    job_service, redaction_service = make_services()
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    result = await tools.create_suggestion(doc_id="job1", text="Jane Doe", category="PII", page_num=0)

    data = json.loads(result)
    assert data["status"] == "created"
    assert "suggestion_id" in data
    assert data["doc_id"] == "job1"


@pytest.mark.asyncio
async def test_create_suggestion_builds_correct_model():
    job_service, redaction_service = make_services()
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    await tools.create_suggestion(
        doc_id="job1",
        text="Jane Doe",
        category="PII",
        page_num=2,
        reasoning="Detected name",
    )

    call_args = redaction_service.add_manual_suggestion.call_args
    suggestion = call_args.args[1] if call_args.args else call_args.kwargs.get("suggestion")
    assert suggestion.source == "agent"
    assert suggestion.rects == []
    assert suggestion.approved is False
    assert suggestion.context == ""
    assert suggestion.reasoning == "Detected name"
    assert suggestion.page_num == 2
    assert suggestion.category == "PII"


@pytest.mark.asyncio
async def test_create_suggestion_uses_default_reasoning():
    job_service, redaction_service = make_services()
    tools = SuggestionTools(job_service=job_service, redaction_service=redaction_service)

    await tools.create_suggestion(doc_id="job1", text="Jane Doe", category="PII", page_num=0)

    call_args = redaction_service.add_manual_suggestion.call_args
    suggestion = call_args.args[1] if call_args.args else call_args.kwargs.get("suggestion")
    assert suggestion.reasoning == "Manually created by agent"