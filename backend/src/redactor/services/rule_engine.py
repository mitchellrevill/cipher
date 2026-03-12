from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RuleMatch:
    document_id: str
    suggestion_id: str
    page_num: int
    text: str
    category: str


class RuleEngine:
    """Evaluate workspace rules against document suggestions."""

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
        affected_docs: list[dict[str, Any]] = []

        for document_id, matches in matches_by_doc.items():
            updated_count = await redaction_service.bulk_update_approvals(
                document_id,
                True,
                suggestion_ids=[match.suggestion_id for match in matches],
            )
            applied_count += updated_count
            affected_docs.append(
                {
                    "document_id": document_id,
                    "match_count": len(matches),
                    "approved_count": updated_count,
                    "pages": sorted({self._to_viewer_page(match.page_num) for match in matches}),
                }
            )

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

    def _to_viewer_page(self, page_num: int) -> int:
        return page_num if page_num >= 1 else page_num + 1