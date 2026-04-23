import asyncio
import uuid
import logging
from backend.app.config import Settings
from backend.app.models import Suggestion, RedactionRect
from backend.app.pipeline.doc_intelligence import DocIntelligenceClient
from backend.app.pipeline.pii_service import PIIServiceClient
from backend.app.pipeline.openai_client import OpenAIRedactionClient
from backend.app.pipeline.fuzzy_matcher import find_text_rects

logger = logging.getLogger(__name__)

async def _get_pii_for_page(page, paragraphs, pii_client, oai_client, config):
    """
    Get PII findings for a page.
    Uses Language Service if ENABLE_PII_SERVICE=True, otherwise GPT.
    Returns list of {text, category, offset, length} dicts.
    """
    page_paras = [
        p for p in paragraphs
        if p.bounding_regions and p.bounding_regions[0].page_number == page.page_number
    ]

    if config.enable_pii_service and pii_client:
        # Parallel Language Service calls per paragraph
        tasks = [pii_client.get_pii(p.content) for p in page_paras]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        findings = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("PII task error", exc_info=result)
            else:
                findings.extend(result)
        return findings
    else:
        # Single GPT call for the whole page text
        page_text = " ".join(p.content for p in page_paras)
        if not page_text.strip():
            return []
        return await oai_client.get_pii_via_llm(page_text)


async def run_pipeline(
    pdf_bytes: bytes,
    user_instructions: str,
    config: Settings,
) -> list[Suggestion]:
    """
    Full async redaction pipeline.
    1. Analyse document + parse instructions concurrently
    2. For each page: PII detection + contextual redaction concurrently
    3. Map findings to PDF coordinates via fuzzy matching
    4. Free the AnalyzeResult from memory
    5. Return sorted Suggestion list
    """
    logger.info("Starting redaction pipeline")

    doc_client = DocIntelligenceClient(
        config.azure_doc_intel_endpoint,
        config.azure_doc_intel_key
    )
    oai_client = OpenAIRedactionClient(
        config.azure_openai_endpoint,
        config.azure_openai_key,
        config.azure_openai_deployment,
        config.azure_openai_api_version
    )
    pii_client = PIIServiceClient(
        config.azure_language_endpoint,
        config.azure_language_key
    ) if config.enable_pii_service else None

    # Step 1: Analyse document and parse instructions concurrently.
    # Use `return_exceptions=True` so missing external services (local dev)
    # do not crash the whole pipeline — fall back to empty analysis or
    # default parsed instructions when services are unavailable.
    analysis_result, parsed_result = await asyncio.gather(
        doc_client.analyse(pdf_bytes),
        oai_client.parse_instructions(user_instructions),
        return_exceptions=True
    )

    # Handle analysis failure gracefully — nothing to process
    if isinstance(analysis_result, Exception):
        logger.error(f"Document analysis failed with {type(analysis_result).__name__}: {str(analysis_result)[:200]}")
        logger.exception("Full document analysis error", exc_info=analysis_result)
        return []

    # Handle instruction parsing failure by using an empty config
    if isinstance(parsed_result, Exception):
        logger.exception("Instruction parsing failed; using defaults")
        parsed_instructions = {}
    else:
        parsed_instructions = parsed_result

    analysis = analysis_result

    pii_exceptions = {e.lower() for e in parsed_instructions.get("exceptions", [])}
    sensitive_rule = parsed_instructions.get("sensitive_content_rules")
    paragraphs = analysis.paragraphs or []

    logger.info(
        "Document analysed: %d pages, %d paragraphs, %d exceptions, contextual rule: %s",
        len(analysis.pages), len(paragraphs),
        len(pii_exceptions), "yes" if sensitive_rule else "no"
    )

    # Step 2: Per-page PII and contextual analysis — all pages in parallel
    async def process_page(page):
        pii_task = _get_pii_for_page(page, paragraphs, pii_client, oai_client, config)
        page_text = analysis.content[
            page.spans[0].offset: page.spans[0].offset + page.spans[0].length
        ] if page.spans else ""

        if sensitive_rule and page_text.strip():
            pii_findings, contextual_findings = await asyncio.gather(
                pii_task,
                oai_client.get_contextual_redactions(page_text, sensitive_rule)
            )
        else:
            pii_findings = await pii_task
            contextual_findings = []

        return pii_findings, contextual_findings

    page_results = await asyncio.gather(
        *[process_page(page) for page in analysis.pages],
        return_exceptions=True
    )

    # Step 3: Map findings to word polygon coordinates.
    # Extract words before deleting analysis — list() holds the word objects explicitly.
    # Note: the word objects themselves are part of the analysis graph, so this is a
    # partial fix; we avoid holding the full AnalyzeResult but the words remain live
    # until words_by_page is deleted after the suggestion-building loop.
    words_by_page = {
        page.page_number - 1: list(page.words)  # list() to hold reference explicitly
        for page in analysis.pages
    }
    del analysis  # AnalyzeResult can now be GC'd (words_by_page holds word objects but not the full result)

    suggestions: list[Suggestion] = []
    for page_num, result in enumerate(page_results):
        if isinstance(result, Exception):
            logger.error("Page %d (1-based) processing failed: %s", page_num + 1, result)
            continue

        pii_findings, contextual_findings = result
        words = words_by_page.get(page_num, [])

        for entity in pii_findings:
            if entity.get("text", "").lower() in pii_exceptions:
                continue
            rects = find_text_rects(entity["text"], words)
            if rects:
                from datetime import datetime
                suggestions.append(Suggestion(
                    id=str(uuid.uuid4()),
                    job_id="",  # Will be set when saved
                    text=entity["text"],
                    category=str(entity.get("category", "Unknown")),
                    reasoning=f"Identified as {entity.get('category', 'PII')}",
                    context="",
                    page_num=page_num,
                    rects=rects,
                    source="ai",
                    created_at=datetime.utcnow()
                ))

        for finding in contextual_findings:
            if finding.get("text", "").lower() in pii_exceptions:
                continue
            rects = find_text_rects(finding["text"], words)
            if rects:
                from datetime import datetime
                suggestions.append(Suggestion(
                    id=str(uuid.uuid4()),
                    job_id="",  # Will be set when saved
                    text=finding["text"],
                    category=str(finding.get("category", "SensitiveContent")),
                    reasoning=finding.get("reasoning", ""),
                    context="",
                    page_num=page_num,
                    rects=rects,
                    source="ai",
                    created_at=datetime.utcnow()
                ))

    del words_by_page  # Free word objects after suggestions are built

    logger.info("Pipeline complete: %d suggestions generated", len(suggestions))

    return sorted(
        suggestions,
        key=lambda s: (s.page_num, s.rects[0].y0 if s.rects else 0)
    )
