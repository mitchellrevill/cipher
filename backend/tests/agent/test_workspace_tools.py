import json
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from redactor.agent.tools.workspace import WorkspaceTools
from redactor.models import Suggestion, RedactionRect
from datetime import datetime


def make_suggestion(text="123-45-6789", suggestion_id="s1", approved=False):
    return Suggestion(
        id=suggestion_id,
        job_id="job1",
        text=text,
        category="PII",
        reasoning="Found test",
        context=f"This is {text}",
        page_num=1,
        rects=[RedactionRect(x0=0, y0=0, x1=1, y1=1)],
        approved=approved,
        source="ai",
        created_at=datetime.utcnow(),
    )


def make_workspace_service(state=None):
    service = AsyncMock()
    service.get_workspace_state.return_value = state or {
        "id": "ws1",
        "name": "Test Workspace",
        "documents": [{"id": "d1"}],
        "rules": [{"id": "r1", "category": "PII", "pattern": "SSN"}],
        "exclusions": [],
    }
    service.create_rule.return_value = {"id": "rule-new", "category": "CreditCard"}
    service.get_rules.return_value = [{"id": "r1", "category": "PII", "pattern": r"\b\d{3}-\d{2}-\d{4}\b"}]
    service.get_exclusions.return_value = []
    service.exclude_document.return_value = {"excluded": True}
    service.add_document.return_value = {"id": "ws1", "document_ids": ["d1", "d2"]}
    service.remove_document.return_value = {"id": "ws1", "document_ids": ["d1"]}
    service.remove_exclusion.return_value = {"id": "ws1", "exclusion_ids": []}
    return service


def make_job_service():
    service = AsyncMock()
    service.get_job.return_value = SimpleNamespace(
        job_id="d1",
        suggestions=[make_suggestion()],
    )
    return service


def make_redaction_service():
    service = AsyncMock()
    service.bulk_update_approvals.return_value = 1
    return service


def make_rule_engine():
    engine = AsyncMock()
    engine.apply_rule.return_value = {"applied_count": 1, "affected_docs": [{"document_id": "d1"}]}
    return engine


@pytest.mark.asyncio
async def test_get_workspace_state_returns_json():
    """get_workspace_state returns JSON string with workspace data."""
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.get_workspace_state(workspace_id="ws1")
    data = json.loads(result)
    assert data["document_count"] == 1
    assert data["rule_count"] == 1


@pytest.mark.asyncio
async def test_get_workspace_state_returns_error_for_missing():
    """get_workspace_state returns error string when workspace not found."""
    service = make_workspace_service(state=None)
    service.get_workspace_state.return_value = None
    tools = WorkspaceTools(workspace_service=service)
    result = await tools.get_workspace_state(workspace_id="missing")
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_create_rule_returns_json():
    """create_rule returns JSON confirmation string."""
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.create_rule(workspace_id="ws1", category="CreditCard", pattern="4[0-9]{15}")
    data = json.loads(result)
    assert "id" in data


@pytest.mark.asyncio
async def test_apply_rule_returns_json():
    """apply_rule returns JSON with applied count."""
    tools = WorkspaceTools(
        workspace_service=make_workspace_service(),
        job_service=make_job_service(),
        redaction_service=make_redaction_service(),
        rule_engine=make_rule_engine(),
    )
    result = await tools.apply_rule(workspace_id="ws1", rule_id="r1")
    data = json.loads(result)
    assert "applied_count" in data


@pytest.mark.asyncio
async def test_exclude_document_returns_json():
    """exclude_document returns JSON confirmation."""
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.exclude_document(workspace_id="ws1", document_id="d1", reason="Exempt")
    data = json.loads(result)
    assert "excluded" in data


@pytest.mark.asyncio
async def test_list_workspace_rules_returns_json():
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.list_workspace_rules(workspace_id="ws1")
    data = json.loads(result)
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_list_workspace_exclusions_returns_json():
    service = make_workspace_service()
    service.get_exclusions.return_value = [{"id": "ex1", "document_id": "d1"}]
    tools = WorkspaceTools(workspace_service=service)
    result = await tools.list_workspace_exclusions(workspace_id="ws1")
    data = json.loads(result)
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_add_and_remove_document_tools_return_json():
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    added = json.loads(await tools.add_document_to_workspace(workspace_id="ws1", document_id="d2"))
    removed = json.loads(await tools.remove_document_from_workspace(workspace_id="ws1", document_id="d2"))
    assert added["id"] == "ws1"
    assert removed["id"] == "ws1"


@pytest.mark.asyncio
async def test_remove_exclusion_returns_json():
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.remove_exclusion(workspace_id="ws1", exclusion_id="ex1")
    data = json.loads(result)
    assert data["id"] == "ws1"


@pytest.mark.asyncio
async def test_workspace_tools_return_error_when_service_missing():
    """All tools return error string when workspace_service is None."""
    tools = WorkspaceTools(workspace_service=None)
    for coro in [
        tools.get_workspace_state(workspace_id="ws1"),
        tools.create_rule(workspace_id="ws1", category="PII", pattern=".*"),
        tools.apply_rule(workspace_id="ws1", rule_id="r1"),
        tools.exclude_document(workspace_id="ws1", document_id="d1"),
        tools.list_workspace_rules(workspace_id="ws1"),
        tools.list_workspace_exclusions(workspace_id="ws1"),
        tools.add_document_to_workspace(workspace_id="ws1", document_id="d1"),
        tools.remove_document_from_workspace(workspace_id="ws1", document_id="d1"),
        tools.remove_exclusion(workspace_id="ws1", exclusion_id="ex1"),
    ]:
        result = await coro
        assert "not configured" in result.lower()


@pytest.mark.asyncio
async def test_apply_rule_returns_error_when_dependencies_missing():
    tools = WorkspaceTools(workspace_service=make_workspace_service())
    result = await tools.apply_rule(workspace_id="ws1", rule_id="r1")
    assert "not configured" in result.lower()


def make_job_with_pdf(doc_id="d1", filename="test.pdf", suggestions=None):
    return SimpleNamespace(job_id=doc_id, filename=filename, suggestions=suggestions or [make_suggestion()])


def make_job_service_with_blob(job=None, pdf_bytes=b""):
    service = AsyncMock()
    service.get_job.return_value = job or make_job_with_pdf()
    blob_client = AsyncMock()
    blob_client.download_original_pdf.return_value = pdf_bytes
    service.blob_client = blob_client
    return service


@pytest.mark.asyncio
async def test_search_workspace_returns_aggregated_results():
    workspace_service = make_workspace_service()
    workspace_service.get_workspace_state.return_value = {
        "id": "ws1",
        "documents": [{"id": "d1"}, {"id": "d2"}],
        "exclusions": [],
    }
    job_service = make_job_service_with_blob()
    tools = WorkspaceTools(workspace_service=workspace_service, job_service=job_service)

    from unittest.mock import MagicMock, patch

    mock_processor = MagicMock()
    mock_processor.search_text.return_value = [{"text": "hit", "page_num": 0, "context": ""}]
    with patch("redactor.agent.tools.workspace.PDFProcessor", return_value=mock_processor):
        result = await tools.search_workspace(workspace_id="ws1", query="hit")

    data = json.loads(result)
    assert data["documents_searched"] == 2
    assert data["documents_with_matches"] == 2


@pytest.mark.asyncio
async def test_search_workspace_skips_excluded_docs():
    workspace_service = make_workspace_service()
    workspace_service.get_workspace_state.return_value = {
        "id": "ws1",
        "documents": [{"id": "d1"}, {"id": "d2"}],
        "exclusions": [{"document_id": "d2"}],
    }
    job_service = make_job_service_with_blob()
    tools = WorkspaceTools(workspace_service=workspace_service, job_service=job_service)

    from unittest.mock import MagicMock, patch

    mock_processor = MagicMock()
    mock_processor.search_text.return_value = [{"text": "hit", "page_num": 0, "context": ""}]
    with patch("redactor.agent.tools.workspace.PDFProcessor", return_value=mock_processor):
        result = await tools.search_workspace(workspace_id="ws1", query="hit")

    data = json.loads(result)
    assert data["documents_searched"] == 1


@pytest.mark.asyncio
async def test_search_workspace_isolates_per_doc_errors():
    workspace_service = make_workspace_service()
    workspace_service.get_workspace_state.return_value = {
        "id": "ws1",
        "documents": [{"id": "d1"}, {"id": "d2"}],
        "exclusions": [],
    }
    job_service = AsyncMock()

    async def get_job_side_effect(doc_id):
        if doc_id == "d1":
            return make_job_with_pdf("d1")
        return make_job_with_pdf("d2")

    job_service.get_job.side_effect = get_job_side_effect
    blob_client = AsyncMock()
    blob_client.download_original_pdf.side_effect = Exception("storage error")
    job_service.blob_client = blob_client

    tools = WorkspaceTools(workspace_service=workspace_service, job_service=job_service)
    result = await tools.search_workspace(workspace_id="ws1", query="anything")
    data = json.loads(result)
    assert data["documents_with_errors"] == 2
    assert data["documents_searched"] == 2


def make_workspace_with_docs():
    service = make_workspace_service()
    service.get_workspace_state.return_value = {
        "id": "ws1",
        "documents": [{"id": "d1"}, {"id": "d2"}],
        "exclusions": [],
    }
    return service


def make_job_service_multi():
    service = AsyncMock()

    async def get_job(doc_id):
        suggestions = [
            make_suggestion(suggestion_id="s1", text="John Smith"),
            Suggestion(
                id="s2",
                job_id=doc_id,
                text="jane.doe@email.com",
                category="Email",
                reasoning="",
                context="",
                page_num=1,
                rects=[],
                approved=True,
                source="ai",
                created_at=datetime.utcnow(),
            ),
        ]
        return SimpleNamespace(job_id=doc_id, filename=f"{doc_id}.pdf", suggestions=suggestions)

    service.get_job.side_effect = get_job
    return service


@pytest.mark.asyncio
async def test_preview_bulk_approval_returns_dry_run_summary():
    redaction_service = make_redaction_service()
    tools = WorkspaceTools(
        workspace_service=make_workspace_with_docs(),
        job_service=make_job_service_multi(),
        redaction_service=redaction_service,
    )

    result = await tools.preview_bulk_approval(workspace_id="ws1", approved=True)

    data = json.loads(result)
    assert data["target_approved"] is True
    assert data["total_would_change"] == 2
    assert len(data["by_document"]) == 2
    redaction_service.bulk_update_approvals.assert_not_called()


@pytest.mark.asyncio
async def test_preview_bulk_approval_filters_by_category():
    tools = WorkspaceTools(
        workspace_service=make_workspace_with_docs(),
        job_service=make_job_service_multi(),
        redaction_service=make_redaction_service(),
    )

    result = await tools.preview_bulk_approval(workspace_id="ws1", approved=True, category="PII")

    data = json.loads(result)
    assert data["total_would_change"] == 2


@pytest.mark.asyncio
async def test_preview_bulk_approval_filters_by_text_pattern():
    tools = WorkspaceTools(
        workspace_service=make_workspace_with_docs(),
        job_service=make_job_service_multi(),
        redaction_service=make_redaction_service(),
    )

    result = await tools.preview_bulk_approval(workspace_id="ws1", approved=True, text_pattern="john")

    data = json.loads(result)
    assert data["total_would_change"] == 2


@pytest.mark.asyncio
async def test_apply_bulk_approval_calls_service_with_explicit_ids():
    redaction_service = make_redaction_service()
    redaction_service.bulk_update_approvals.return_value = 1
    tools = WorkspaceTools(
        workspace_service=make_workspace_with_docs(),
        job_service=make_job_service_multi(),
        redaction_service=redaction_service,
    )

    result = await tools.apply_bulk_approval(workspace_id="ws1", approved=True)

    data = json.loads(result)
    assert data["total_updated"] >= 2
    for call in redaction_service.bulk_update_approvals.call_args_list:
        ids_arg = call.args[2] if len(call.args) > 2 else call.kwargs.get("suggestion_ids")
        assert ids_arg is not None and len(ids_arg) > 0


@pytest.mark.asyncio
async def test_apply_bulk_approval_skips_docs_with_no_matches():
    workspace_service = make_workspace_with_docs()
    redaction_service = make_redaction_service()
    job_service = AsyncMock()

    async def get_job(doc_id):
        suggestion = make_suggestion(suggestion_id="s1", approved=True)
        return SimpleNamespace(job_id=doc_id, filename=f"{doc_id}.pdf", suggestions=[suggestion])

    job_service.get_job.side_effect = get_job
    tools = WorkspaceTools(
        workspace_service=workspace_service,
        job_service=job_service,
        redaction_service=redaction_service,
    )

    result = await tools.apply_bulk_approval(workspace_id="ws1", approved=True)

    data = json.loads(result)
    assert data["total_updated"] == 0
    redaction_service.bulk_update_approvals.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_create_suggestions_adds_to_matching_docs():
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 144), "John Smith visited today")
    pdf_bytes = document.write()
    document.close()

    workspace_service = make_workspace_with_docs()
    redaction_service = make_redaction_service()
    redaction_service.add_suggestions = AsyncMock(return_value=1)

    job_service = AsyncMock()

    async def get_job(doc_id):
        return SimpleNamespace(job_id=doc_id, filename=f"{doc_id}.pdf", suggestions=[])

    job_service.get_job.side_effect = get_job
    blob_client = AsyncMock()
    blob_client.download_original_pdf.return_value = pdf_bytes
    job_service.blob_client = blob_client

    tools = WorkspaceTools(
        workspace_service=workspace_service,
        job_service=job_service,
        redaction_service=redaction_service,
    )

    result = await tools.bulk_create_suggestions(workspace_id="ws1", text="John Smith", category="PII")

    data = json.loads(result)
    assert data["total_added"] >= 1
    redaction_service.add_suggestions.assert_called()


@pytest.mark.asyncio
async def test_bulk_create_suggestions_records_no_match_for_missing_text():
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 144), "Completely different content")
    pdf_bytes = document.write()
    document.close()

    workspace_service = make_workspace_with_docs()
    workspace_service.get_workspace_state.return_value = {
        "id": "ws1",
        "documents": [{"id": "d1"}],
        "exclusions": [],
    }
    redaction_service = make_redaction_service()
    redaction_service.add_suggestions = AsyncMock(return_value=0)
    job_service = AsyncMock()
    job_service.get_job.return_value = SimpleNamespace(job_id="d1", filename="d1.pdf", suggestions=[])
    blob_client = AsyncMock()
    blob_client.download_original_pdf.return_value = pdf_bytes
    job_service.blob_client = blob_client

    tools = WorkspaceTools(
        workspace_service=workspace_service,
        job_service=job_service,
        redaction_service=redaction_service,
    )

    result = await tools.bulk_create_suggestions(workspace_id="ws1", text="zzz_nomatch", category="PII")

    data = json.loads(result)
    assert data["total_added"] == 0
    entry = data["by_document"][0]
    assert entry["no_match"] is True
    redaction_service.add_suggestions.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_create_suggestions_skips_excluded_docs():
    workspace_service = make_workspace_with_docs()
    workspace_service.get_workspace_state.return_value = {
        "id": "ws1",
        "documents": [{"id": "d1"}, {"id": "d2"}],
        "exclusions": [{"document_id": "d2"}],
    }
    redaction_service = make_redaction_service()
    redaction_service.add_suggestions = AsyncMock(return_value=0)
    job_service = AsyncMock()
    job_service.get_job.return_value = SimpleNamespace(job_id="d1", filename="d1.pdf", suggestions=[])
    blob_client = AsyncMock()
    blob_client.download_original_pdf.return_value = b""
    job_service.blob_client = blob_client

    tools = WorkspaceTools(
        workspace_service=workspace_service,
        job_service=job_service,
        redaction_service=redaction_service,
    )

    result = await tools.bulk_create_suggestions(workspace_id="ws1", text="anything", category="PII")

    data = json.loads(result)
    assert len(data["by_document"]) == 1
    assert data["by_document"][0]["doc_id"] == "d1"
