from __future__ import annotations

from datetime import datetime
import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.models import Suggestion
from app.pdf.processor import PDFProcessor


@dataclass(slots=True)
class RuleMatch:
    document_id: str
    suggestion_id: str
    page_num: int
    text: str
    category: str


class RuleEngine:
    """Evaluate workspace rules against document suggestions and raw PDF text."""

    COMMON_RULE_PATTERNS: dict[str, tuple[str, str]] = {
        "ssn": (r"\b\d{3}-\d{2}-\d{4}\b", "PII"),
        "social security": (r"\b\d{3}-\d{2}-\d{4}\b", "PII"),
        "email": (r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "Contact"),
        "phone": (r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b", "Contact"),
        "account": (r"\b\d{8,17}\b", "Financial"),
        "credit card": (r"\b(?:\d[ -]*?){13,16}\b", "Financial"),
    }

    def infer_rule_definition(self, message: str) -> dict[str, Any] | None:
        lowered = message.lower()

        for keyword, (pattern, category) in self.COMMON_RULE_PATTERNS.items():
            if keyword in lowered:
                return {
                    "pattern": pattern,
                    "category": category,
                    "confidence_threshold": 0.8,
                }

        quoted = self._extract_quoted_text(message)
        if quoted:
            return {
                "pattern": re.escape(quoted),
                "category": "Custom",
                "confidence_threshold": 0.8,
            }

        return None

    def resolve_rule(self, message: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not rules:
            return None

        lowered = message.lower()
        for rule in rules:
            if rule.get("id", "").lower() in lowered:
                return rule
            if rule.get("category", "").lower() in lowered:
                return rule
            pattern = str(rule.get("pattern", ""))
            if pattern and pattern.lower() in lowered:
                return rule

        return rules[-1]

    def find_matches(
        self,
        rule: dict[str, Any],
        jobs_by_id: dict[str, Any],
        excluded_doc_ids: set[str] | None = None,
    ) -> dict[str, list[RuleMatch]]:
        pattern = rule.get("pattern")
        if not pattern:
            return {}

        excluded = excluded_doc_ids or set()
        regex = re.compile(pattern, re.IGNORECASE)
        matches_by_doc: dict[str, list[RuleMatch]] = {}

        for document_id, job in jobs_by_id.items():
            if document_id in excluded or not job:
                continue

            document_matches: list[RuleMatch] = []
            for suggestion in getattr(job, "suggestions", []):
                haystacks = [
                    suggestion.text or "",
                    suggestion.context or "",
                    suggestion.reasoning or "",
                    suggestion.category or "",
                ]
                if any(regex.search(haystack) for haystack in haystacks):
                    document_matches.append(
                        RuleMatch(
                            document_id=document_id,
                            suggestion_id=suggestion.id,
                            page_num=suggestion.page_num,
                            text=suggestion.text,
                            category=suggestion.category,
                        )
                    )

            if document_matches:
                matches_by_doc[document_id] = document_matches

        return matches_by_doc

    def find_pdf_matches(
        self,
        rule: dict[str, Any],
        pdf_bytes_by_id: dict[str, bytes],
        excluded_doc_ids: set[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        pattern = rule.get("pattern")
        if not pattern:
            return {}

        excluded = excluded_doc_ids or set()
        matches_by_doc: dict[str, list[dict[str, Any]]] = {}
        for document_id, pdf_bytes in pdf_bytes_by_id.items():
            if document_id in excluded or not pdf_bytes:
                continue

            processor = PDFProcessor(pdf_bytes)
            matches = processor.search_text(pattern)
            if matches:
                matches_by_doc[document_id] = matches

        return matches_by_doc

    async def apply_rule(
        self,
        rule: dict[str, Any],
        jobs_by_id: dict[str, Any],
        redaction_service,
        excluded_doc_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        excluded = excluded_doc_ids or set()
        matches_by_doc = self.find_matches(rule, jobs_by_id, excluded_doc_ids=excluded)
        applied_count = 0
        affected_index: dict[str, dict[str, Any]] = {}

        def record_affected(
            document_id: str,
            *,
            match_count: int = 0,
            approved_count: int = 0,
            created_count: int = 0,
            pages: list[int] | None = None,
        ):
            payload = affected_index.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "match_count": 0,
                    "approved_count": 0,
                    "created_count": 0,
                    "pages": set(),
                },
            )
            payload["match_count"] += match_count
            payload["approved_count"] += approved_count
            payload["created_count"] += created_count
            if pages:
                payload["pages"].update(pages)

        for document_id, matches in matches_by_doc.items():
            updated_count = await redaction_service.bulk_update_approvals(
                document_id,
                True,
                suggestion_ids=[match.suggestion_id for match in matches],
            )
            applied_count += updated_count
            record_affected(
                document_id,
                match_count=len(matches),
                approved_count=updated_count,
                pages=sorted({self._to_viewer_page(match.page_num) for match in matches}),
            )

        blob_client = getattr(redaction_service, "blob_client", None)
        if blob_client:
            pdf_bytes_by_id: dict[str, bytes] = {}
            for document_id in jobs_by_id:
                if document_id in excluded:
                    continue
                try:
                    pdf_bytes = await blob_client.download_original_pdf(document_id)
                except Exception:
                    continue
                if not isinstance(pdf_bytes, (bytes, bytearray, memoryview)):
                    continue
                pdf_bytes_by_id[document_id] = bytes(pdf_bytes)

            pdf_matches_by_doc = self.find_pdf_matches(rule, pdf_bytes_by_id, excluded_doc_ids=excluded)

            for document_id, pdf_matches in pdf_matches_by_doc.items():
                job = jobs_by_id.get(document_id)
                existing_keys = {
                    self._suggestion_signature(suggestion)
                    for suggestion in getattr(job, "suggestions", [])
                }
                new_suggestions: list[Suggestion] = []

                for match in pdf_matches:
                    suggestion = Suggestion(
                        id=str(uuid.uuid4()),
                        job_id=document_id,
                        text=match["text"],
                        category=str(rule.get("category", "Custom")),
                        reasoning=f"Matched workspace rule pattern: {rule.get('pattern', '')}",
                        context=match.get("context", ""),
                        page_num=match["page_num"],
                        rects=match["rects"],
                        approved=True,
                        source="agent",
                        created_at=datetime.utcnow(),
                    )
                    signature = self._suggestion_signature(suggestion)
                    if signature in existing_keys:
                        continue
                    existing_keys.add(signature)
                    new_suggestions.append(suggestion)

                created_count = 0
                if new_suggestions and hasattr(redaction_service, "add_suggestions"):
                    created_count = await redaction_service.add_suggestions(document_id, new_suggestions)
                    applied_count += created_count
                    record_affected(
                        document_id,
                        match_count=created_count,
                        approved_count=created_count,
                        created_count=created_count,
                        pages=sorted({self._to_viewer_page(suggestion.page_num) for suggestion in new_suggestions}),
                    )

                if job is not None and new_suggestions:
                    job.suggestions.extend(new_suggestions)

        affected_docs = [
            {
                **payload,
                "pages": sorted(payload["pages"]),
            }
            for payload in affected_index.values()
        ]

        return {
            "rule_id": rule.get("id"),
            "pattern": rule.get("pattern"),
            "applied_count": applied_count,
            "affected_docs": affected_docs,
            "skipped": sorted(excluded),
        }

    def _extract_quoted_text(self, message: str) -> str | None:
        match = re.search(r'"([^"]+)"|\'([^\']+)\'', message)
        if not match:
            return None
        return next(group for group in match.groups() if group)

    def _suggestion_signature(self, suggestion: Suggestion) -> tuple:
        return (
            suggestion.page_num,
            suggestion.category.lower(),
            suggestion.text.strip().lower(),
            tuple(
                (
                    round(rect.x0, 3),
                    round(rect.y0, 3),
                    round(rect.x1, 3),
                    round(rect.y1, 3),
                )
                for rect in suggestion.rects
            ),
        )

    def _to_viewer_page(self, page_num: int) -> int:
        return page_num if page_num >= 1 else page_num + 1