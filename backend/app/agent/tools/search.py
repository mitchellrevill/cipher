import json
import logging
import re
from collections import Counter
from typing import Annotated, Awaitable, Callable, Optional
from agent_framework import tool
from pydantic import Field
from backend.app.pdf.processor import PDFProcessor

logger = logging.getLogger(__name__)


def _build_query_variants(query: str) -> list[tuple[str, str]]:
    """
    Return a list of (strategy_name, regex_pattern) pairs ordered from strictest
    to most permissive.  Used to progressively widen a raw-text PDF search.
    """
    q = query.strip()
    escaped = re.escape(q)
    words = [w for w in re.split(r"[\s\-./,]+", q) if len(w) > 1]

    variants: list[tuple[str, str]] = [
        # 1. Word-boundary exact match
        ("exact_word", rf"\b{escaped}\b"),
        # 2. Plain substring (no word boundary) for short/abbreviation queries
        ("exact_substring", escaped),
    ]

    if len(words) > 1:
        # 3. All words must appear on the same page (AND-joined via lookahead)
        lookaheads = "".join(f"(?=.*{re.escape(w)})" for w in words)
        variants.append(("all_words", f"(?i){lookaheads}"))

        # 4. Any word present (OR-joined)
        any_pattern = "|".join(rf"\b{re.escape(w)}\b" for w in words)
        variants.append(("any_word", any_pattern))

        # 5. Longest individual word (best single-token signal)
        longest = max(words, key=len)
        variants.append(("longest_word", rf"\b{re.escape(longest)}\b"))
    else:
        # Single-word: try without word boundary as last resort
        variants.append(("word_partial", re.escape(words[0]) if words else escaped))

    return variants


class DocumentTools:
    """Tools for searching within a single redaction document."""

    def __init__(self, job_service, event_emitter: Optional[Callable[..., None]] = None):
        self.job_service = job_service
        self.event_emitter = event_emitter

    def _emit(self, event_type: str, tool_name: str, summary: Optional[str] = None):
        if self.event_emitter:
            self.event_emitter(event_type=event_type, tool_name=tool_name, summary=summary)

    def _summarize_result(self, result: str) -> str:
        if result.startswith("Error:"):
            return result

        try:
            payload = json.loads(result)
        except Exception:
            return result[:160]

        if isinstance(payload, dict):
            if "count" in payload and "document_id" in payload:
                count = payload["count"]
                strategy = payload.get("match_strategy", "")
                searched = payload.get("searched", "")
                if count == 0:
                    return f"No matches found in {payload['document_id']}"
                suffix = f" via {strategy}" if strategy and strategy != "exact" else ""
                source = " (raw PDF text)" if searched == "pdf_text" else ""
                return f"Found {count} results in {payload['document_id']}{source}{suffix}"
            if "suggestion_count" in payload and "document_id" in payload:
                return f"Summarized {payload['suggestion_count']} suggestions for {payload['document_id']}"
            if "suggestion" in payload:
                suggestion = payload["suggestion"]
                return f"Loaded suggestion {suggestion.get('id', 'unknown')}"

        return result[:160]

    async def _run_tool(self, tool_name: str, action: Callable[[], Awaitable[str]]) -> str:
        self._emit("tool_start", tool_name)
        try:
            result = await action()
            self._emit("tool_result", tool_name, self._summarize_result(result))
            return result
        except Exception as exc:
            self._emit("tool_error", tool_name, str(exc))
            raise

    async def _get_job(self, doc_id: str):
        if not self.job_service:
            return None, "Error: job service not configured"

        job = await self.job_service.get_job(doc_id)
        if not job:
            return None, f"Error: document '{doc_id}' not found"
        return job, None

    @tool(approval_mode="never_require")
    async def search_document(
        self,
        query: Annotated[str, Field(description="Text to search for in the raw document content")],
        doc_id: Annotated[str, Field(description="Document ID to search in")],
        limit: Annotated[int, Field(description="Maximum number of matching results to return")] = 25,
        include_suggestions: Annotated[bool, Field(description="Also cross-reference existing redaction suggestions. Use list_document_suggestions instead for browsing all suggestions.")] = False,
    ) -> str:
        """
        Search the raw PDF page text for the given query. Use this to find content
        that may not yet have a redaction suggestion — ideal for discovery queries
        like "find names, emails, or phone numbers I may have missed".

        Automatically retries with progressively fuzzy strategies:
          1. Word-boundary regex in raw PDF text
          2. Any-word regex in raw PDF text
          3. Plain substring in raw PDF text

        When include_suggestions=True, also cross-references existing redaction
        suggestions if the PDF search finds nothing.

        Returns results from the first strategy that yields matches, along with the
        strategy name so the caller knows how confident the results are.
        """
        async def action() -> str:
            try:
                job, error = await self._get_job(doc_id)
                if error:
                    return error

                query_stripped = query.strip()
                if not query_stripped:
                    return "Error: query must not be empty"

                capped_limit = max(1, min(limit, 100))

                # ── PDF raw-text search (primary) ──────────────────────────────
                blob_client = getattr(self.job_service, "blob_client", None)
                pdf_bytes: bytes | None = None
                if blob_client:
                    try:
                        raw = await blob_client.download_original_pdf(doc_id)
                        if isinstance(raw, bytes) and raw:
                            pdf_bytes = raw
                    except Exception:
                        logger.debug("Could not download PDF for raw text search of %s", doc_id)

                if pdf_bytes:
                    processor = PDFProcessor(pdf_bytes)
                    pdf_results: list[dict] = []
                    pdf_strategy = "none"
                    for strategy_name, pattern in _build_query_variants(query_stripped):
                        try:
                            matches = processor.search_text(pattern)
                        except re.error:
                            continue
                        if matches:
                            pdf_results = [
                                {
                                    "text": m["text"],
                                    "page": m["page_num"],
                                    "context": m.get("context", ""),
                                    "source": "pdf_text",
                                    "match_strategy": strategy_name,
                                }
                                for m in matches[:capped_limit]
                            ]
                            pdf_strategy = strategy_name
                            break

                    if pdf_results:
                        return json.dumps({
                            "query": query,
                            "document_id": doc_id,
                            "results": pdf_results,
                            "count": len(pdf_results),
                            "limit": capped_limit,
                            "searched": "pdf_text",
                            "match_strategy": pdf_strategy,
                        })

                # ── Suggestion cross-reference (opt-in) ────────────────────────
                if include_suggestions:
                    words = [w for w in re.split(r"[\s\-./,]+", query_stripped) if len(w) > 1]
                    all_suggestions = list(getattr(job, "suggestions", []))

                    def _match_suggestion(suggestion, matcher) -> bool:
                        haystacks = [
                            suggestion.text or "",
                            suggestion.context or "",
                            suggestion.reasoning or "",
                        ]
                        return any(matcher(h) for h in haystacks)

                    def _collect(matcher, strategy_name: str) -> list[dict]:
                        results = []
                        for s in all_suggestions:
                            if _match_suggestion(s, matcher):
                                results.append({
                                    "id": s.id,
                                    "text": s.text,
                                    "category": s.category,
                                    "page": s.page_num,
                                    "context": s.context,
                                    "reasoning": s.reasoning,
                                    "approved": s.approved,
                                    "source": "suggestion",
                                    "match_strategy": strategy_name,
                                })
                            if len(results) >= capped_limit:
                                break
                        return results

                    q_lower = query_stripped.lower()
                    suggestion_strategies: list = [
                        ("exact", lambda h: q_lower in h.lower()),
                    ]
                    if len(words) > 1:
                        suggestion_strategies.append(
                            ("all_words", lambda h: all(w.lower() in h.lower() for w in words))
                        )
                        suggestion_strategies.append(
                            ("any_word", lambda h: any(w.lower() in h.lower() for w in words))
                        )
                    else:
                        clean = re.sub(r"[^\w]", "", query_stripped).lower()
                        if clean and clean != q_lower:
                            suggestion_strategies.append(
                                ("clean_word", lambda h: clean in h.lower())
                            )

                    for strategy_name, matcher in suggestion_strategies:
                        hits = _collect(matcher, strategy_name)
                        if hits:
                            return json.dumps({
                                "query": query,
                                "document_id": doc_id,
                                "results": hits,
                                "count": len(hits),
                                "limit": capped_limit,
                                "searched": "suggestions",
                                "match_strategy": strategy_name,
                            })

                # ── Nothing found ──────────────────────────────────────────────
                return json.dumps({
                    "query": query,
                    "document_id": doc_id,
                    "results": [],
                    "count": 0,
                    "limit": capped_limit,
                    "searched": "pdf_text" if not include_suggestions else "pdf_text_and_suggestions",
                    "match_strategy": "none",
                    "note": (
                        "No matches found in the raw document text. "
                        "The text may not appear in this document, or the PDF is not stored."
                    ),
                })
            except Exception as e:
                logger.exception("Error in search_document")
                return f"Error: search failed — {e}"

        return await self._run_tool("search_document", action)

    @tool(approval_mode="never_require")
    async def get_document_summary(
        self,
        doc_id: Annotated[str, Field(description="Document ID to summarize")],
    ) -> str:
        """Summarize the redaction state of a document, including category counts and approval status."""
        async def action() -> str:
            try:
                job, error = await self._get_job(doc_id)
                if error:
                    return error

                suggestions = list(getattr(job, "suggestions", []))
                categories = Counter(suggestion.category for suggestion in suggestions if suggestion.category)
                pages = Counter(suggestion.page_num for suggestion in suggestions)

                return json.dumps({
                    "document_id": doc_id,
                    "filename": getattr(job, "filename", None),
                    "status": getattr(getattr(job, "status", None), "value", getattr(job, "status", None)),
                    "suggestion_count": len(suggestions),
                    "approved_count": sum(1 for suggestion in suggestions if suggestion.approved),
                    "pending_count": sum(1 for suggestion in suggestions if not suggestion.approved),
                    "categories": dict(categories),
                    "top_pages": [
                        {"page": page, "count": count}
                        for page, count in pages.most_common(5)
                    ],
                })
            except Exception as e:
                logger.exception("Error in get_document_summary")
                return f"Error: summary failed — {e}"

        return await self._run_tool("get_document_summary", action)

    @tool(approval_mode="never_require")
    async def list_document_suggestions(
        self,
        doc_id: Annotated[str, Field(description="Document ID to inspect")],
        category: Annotated[Optional[str], Field(description="Optional category filter such as PII or Financial")] = None,
        approved: Annotated[Optional[bool], Field(description="Optional approval filter")] = None,
        page: Annotated[Optional[int], Field(description="Optional page number filter")] = None,
        limit: Annotated[int, Field(description="Maximum number of suggestions to return")] = 25,
    ) -> str:
        """List suggestions in a document with optional filters for category, approval state, and page."""
        async def action() -> str:
            try:
                job, error = await self._get_job(doc_id)
                if error:
                    return error

                capped_limit = max(1, min(limit, 100))
                results = []
                for suggestion in getattr(job, "suggestions", []):
                    if category and suggestion.category.lower() != category.lower():
                        continue
                    if approved is not None and suggestion.approved is not approved:
                        continue
                    if page is not None and suggestion.page_num != page:
                        continue

                    results.append({
                        "id": suggestion.id,
                        "text": suggestion.text,
                        "category": suggestion.category,
                        "page": suggestion.page_num,
                        "approved": suggestion.approved,
                        "context": suggestion.context,
                    })
                    if len(results) >= capped_limit:
                        break

                return json.dumps({
                    "document_id": doc_id,
                    "filters": {
                        "category": category,
                        "approved": approved,
                        "page": page,
                        "limit": capped_limit,
                    },
                    "count": len(results),
                    "results": results,
                })
            except Exception as e:
                logger.exception("Error in list_document_suggestions")
                return f"Error: listing suggestions failed — {e}"

        return await self._run_tool("list_document_suggestions", action)

    @tool(approval_mode="never_require")
    async def get_suggestion_details(
        self,
        doc_id: Annotated[str, Field(description="Document ID containing the suggestion")],
        suggestion_id: Annotated[str, Field(description="Suggestion ID to inspect")],
    ) -> str:
        """Return the details of a single suggestion in a document."""
        async def action() -> str:
            try:
                job, error = await self._get_job(doc_id)
                if error:
                    return error

                for suggestion in getattr(job, "suggestions", []):
                    if suggestion.id == suggestion_id:
                        return json.dumps({
                            "document_id": doc_id,
                            "suggestion": {
                                "id": suggestion.id,
                                "text": suggestion.text,
                                "category": suggestion.category,
                                "reasoning": suggestion.reasoning,
                                "context": suggestion.context,
                                "page": suggestion.page_num,
                                "approved": suggestion.approved,
                                "rects": [rect.model_dump() for rect in suggestion.rects],
                            },
                        })

                return f"Error: suggestion '{suggestion_id}' not found in document '{doc_id}'"
            except Exception as e:
                logger.exception("Error in get_suggestion_details")
                return f"Error: suggestion lookup failed — {e}"

        return await self._run_tool("get_suggestion_details", action)
