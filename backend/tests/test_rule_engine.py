from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import fitz

from redactor.models import RedactionRect, Suggestion
from redactor.services.rule_engine import RuleEngine


def _suggestion(*, suggestion_id: str, text: str, page_num: int = 1, approved: bool = False) -> Suggestion:
    return Suggestion(
        id=suggestion_id,
        job_id="job-1",
        text=text,
        category="PII",
        reasoning="Matched content",
        context=text,
        page_num=page_num,
        rects=[RedactionRect(x0=0, y0=0, x1=1, y1=1)],
        approved=approved,
        source="ai",
        created_at=datetime.utcnow(),
    )


def test_infer_rule_definition_for_ssn():
    engine = RuleEngine()

    rule = engine.infer_rule_definition("Create a rule to redact SSNs across this workspace")

    assert rule is not None
    assert rule["category"] == "PII"
    assert "\\d{3}-\\d{2}-\\d{4}" in rule["pattern"]


def test_find_matches_respects_exclusions():
    engine = RuleEngine()
    rule = {"id": "rule-ssn", "pattern": r"\b\d{3}-\d{2}-\d{4}\b", "category": "PII"}
    jobs_by_id = {
        "doc-1": SimpleNamespace(suggestions=[_suggestion(suggestion_id="s1", text="123-45-6789")]),
        "doc-2": SimpleNamespace(suggestions=[_suggestion(suggestion_id="s2", text="987-65-4321")]),
    }

    matches = engine.find_matches(rule, jobs_by_id, excluded_doc_ids={"doc-2"})

    assert list(matches.keys()) == ["doc-1"]
    assert matches["doc-1"][0].suggestion_id == "s1"


@pytest.mark.asyncio
async def test_apply_rule_bulk_approves_matches():
    engine = RuleEngine()
    redaction_service = AsyncMock()
    redaction_service.bulk_update_approvals.return_value = 1
    rule = {"id": "rule-ssn", "pattern": r"\b\d{3}-\d{2}-\d{4}\b", "category": "PII"}
    jobs_by_id = {
        "doc-1": SimpleNamespace(suggestions=[_suggestion(suggestion_id="s1", text="123-45-6789")]),
    }

    result = await engine.apply_rule(rule, jobs_by_id, redaction_service=redaction_service)

    assert result["applied_count"] == 1
    assert result["affected_docs"][0]["document_id"] == "doc-1"
    redaction_service.bulk_update_approvals.assert_awaited_once_with("doc-1", True, suggestion_ids=["s1"])


def _sample_searchable_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), text, fontsize=12)
    try:
        return doc.write()
    finally:
        doc.close()


@pytest.mark.asyncio
async def test_apply_rule_creates_agent_suggestions_from_page_text():
    engine = RuleEngine()
    pdf_bytes = _sample_searchable_pdf_bytes("GP appears twice. Another GP appears here.")
    blob_client = AsyncMock()
    blob_client.download_original_pdf.return_value = pdf_bytes
    redaction_service = AsyncMock()
    redaction_service.blob_client = blob_client
    redaction_service.bulk_update_approvals.return_value = 0
    redaction_service.add_suggestions.return_value = 2
    rule = {"id": "rule-gp", "pattern": r"\bgp\b", "category": "Custom"}
    jobs_by_id = {
        "doc-1": SimpleNamespace(suggestions=[]),
    }

    result = await engine.apply_rule(rule, jobs_by_id, redaction_service=redaction_service)

    assert result["applied_count"] == 2
    assert result["affected_docs"][0]["created_count"] == 2
    redaction_service.add_suggestions.assert_awaited_once()