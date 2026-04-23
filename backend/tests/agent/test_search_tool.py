import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agent.tools.search import DocumentTools, _build_query_variants
from app.models import Suggestion, RedactionRect
from datetime import datetime


def make_suggestion(text="test data", category="PII"):
    return Suggestion(
        id="s1",
        job_id="job1",
        text=text,
        category=category,
        reasoning="Found test",
        context=f"This is {text}",
        page_num=0,
        rects=[RedactionRect(x0=0, y0=0, x1=1, y1=1)],
        approved=False,
        source="ai",
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_search_document_finds_text():
    """search_document returns JSON with matching suggestions when include_suggestions=True."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("test data")]
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="test", doc_id="job1", include_suggestions=True)
    data = json.loads(result)
    assert data["count"] == 1
    assert "test" in data["results"][0]["text"]


@pytest.mark.asyncio
async def test_search_document_respects_limit():
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("test one"), make_suggestion("test two", category="Contact")]
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="test", doc_id="job1", limit=1, include_suggestions=True)
    data = json.loads(result)
    assert data["count"] == 1
    assert data["limit"] == 1


@pytest.mark.asyncio
async def test_search_document_returns_empty_when_no_match():
    """search_document returns zero results when nothing matches."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("unrelated content")]
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="zzznomatch", doc_id="job1")
    data = json.loads(result)
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_search_document_returns_error_for_missing_job():
    """search_document returns error string when job not found."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = None
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="test", doc_id="missing")
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_search_document_returns_error_when_service_missing():
    """search_document returns error string when service is not configured."""
    tools = DocumentTools(job_service=None)
    result = await tools.search_document(query="test", doc_id="doc1")
    assert "not configured" in result.lower()


@pytest.mark.asyncio
async def test_search_document_returns_error_for_empty_query():
    """search_document returns error string when query is empty."""
    mock_job_service = AsyncMock()
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="", doc_id="doc1")
    assert "empty" in result.lower()


@pytest.mark.asyncio
async def test_get_document_summary_returns_json():
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        filename="test.pdf",
        status=MagicMock(value="complete"),
        suggestions=[make_suggestion("test data"), make_suggestion("other", category="Contact")],
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.get_document_summary(doc_id="job1")
    data = json.loads(result)
    assert data["document_id"] == "job1"
    assert data["suggestion_count"] == 2


@pytest.mark.asyncio
async def test_list_document_suggestions_filters_results():
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[
            make_suggestion("one", category="PII"),
            make_suggestion("two", category="Contact"),
        ],
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.list_document_suggestions(doc_id="job1", category="Contact")
    data = json.loads(result)
    assert data["count"] == 1
    assert data["results"][0]["category"] == "Contact"


@pytest.mark.asyncio
async def test_get_suggestion_details_returns_single_suggestion():
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("test data", category="PII")],
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.get_suggestion_details(doc_id="job1", suggestion_id="s1")
    data = json.loads(result)
    assert data["suggestion"]["id"] == "s1"


@pytest.mark.asyncio
async def test_get_suggestion_details_returns_error_when_missing():
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(job_id="job1", suggestions=[])
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.get_suggestion_details(doc_id="job1", suggestion_id="missing")
    assert "not found" in result.lower()


# ─── Fuzzy / multi-strategy search tests ─────────────────────────────────────

def test_build_query_variants_single_word():
    variants = _build_query_variants("gp")
    names = [name for name, _ in variants]
    assert "exact_word" in names
    assert "exact_substring" in names


def test_build_query_variants_multi_word():
    variants = _build_query_variants("general practitioner")
    names = [name for name, _ in variants]
    assert "exact_word" in names
    assert "all_words" in names
    assert "any_word" in names


@pytest.mark.asyncio
async def test_search_document_falls_back_to_any_word():
    """With include_suggestions=True, falls back to any-word matching in suggestions."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("General Practitioner note")]
    )
    tools = DocumentTools(job_service=mock_job_service)
    # Query is an abbreviation - exact will miss; any_word on "practitioner" should hit
    result = await tools.search_document(query="practitioner notes", doc_id="job1", include_suggestions=True)
    data = json.loads(result)
    assert data["count"] == 1
    # Strategy should NOT be "exact" since "practitioner notes" != "General Practitioner note"
    assert data["match_strategy"] in ("all_words", "any_word")


@pytest.mark.asyncio
async def test_search_document_includes_match_strategy():
    """Result payload always includes match_strategy field."""
    mock_job_service = AsyncMock()
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("some PII content")]
    )
    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="PII", doc_id="job1")
    data = json.loads(result)
    assert "match_strategy" in data


@pytest.mark.asyncio
async def test_search_document_pdf_fallback_when_no_suggestions_match(tmp_path):
    """Searches raw PDF text by default (primary path)."""
    import fitz

    # Create a tiny in-memory PDF with known text
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 144), "General Practitioner referral letter")
    pdf_bytes = doc.write()
    doc.close()

    blob_client = AsyncMock()
    blob_client.download_original_pdf.return_value = pdf_bytes

    mock_job_service = AsyncMock()
    mock_job_service.blob_client = blob_client
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[]  # no existing suggestions
    )

    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="Practitioner", doc_id="job1")
    data = json.loads(result)
    assert data["count"] > 0
    assert data["searched"] == "pdf_text"


@pytest.mark.asyncio
async def test_search_document_returns_no_matches_note_when_truly_absent():
    """Returns count=0 with a helpful note when nothing is found anywhere."""
    blob_client = AsyncMock()
    blob_client.download_original_pdf.side_effect = Exception("not found")

    mock_job_service = AsyncMock()
    mock_job_service.blob_client = blob_client
    mock_job_service.get_job.return_value = MagicMock(
        job_id="job1",
        suggestions=[make_suggestion("unrelated content")]
    )

    tools = DocumentTools(job_service=mock_job_service)
    result = await tools.search_document(query="zzznomatch", doc_id="job1")
    data = json.loads(result)
    assert data["count"] == 0
    assert "note" in data
