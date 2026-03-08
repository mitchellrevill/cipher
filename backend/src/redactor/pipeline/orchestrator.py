import asyncio
import uuid
import logging
from redactor.config import Settings
from redactor.models import Suggestion, RedactionRect
from redactor.pipeline.doc_intelligence import DocIntelligenceClient
from redactor.pipeline.pii_service import PIIServiceClient
from redactor.pipeline.openai_client import OpenAIRedactionClient
from redactor.pipeline.fuzzy_matcher import find_text_rects

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
                logger.exception("PII task error: %s", result)
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

    # Step 1: Analyse document and parse instructions concurrently
    analysis, parsed_instructions = await asyncio.gather(
        doc_client.analyse(pdf_bytes),
        oai_client.parse_instructions(user_instructions)
    )

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

    # Step 3: Map findings to word polygon coordinates
    words_by_page = {
        page.page_number - 1: page.words
        for page in analysis.pages
    }

    # Free the large AnalyzeResult from memory
    del analysis

    suggestions: list[Suggestion] = []
    for page_num, result in enumerate(page_results):
        if isinstance(result, Exception):
            logger.error("Page %d processing failed: %s", page_num, result)
            continue

        pii_findings, contextual_findings = result
        words = words_by_page.get(page_num, [])

        for entity in pii_findings:
            if entity.get("text", "").lower() in pii_exceptions:
                continue
            rects = find_text_rects(entity["text"], words)
            if rects:
                suggestions.append(Suggestion(
                    id=str(uuid.uuid4()),
                    text=entity["text"],
                    category=str(entity.get("category", "Unknown")),
                    reasoning=f"Identified as {entity.get('category', 'PII')}",
                    context="",
                    page_num=page_num,
                    rects=rects,
                    source="ai"
                ))

        for finding in contextual_findings:
            if finding.get("text", "").lower() in pii_exceptions:
                continue
            rects = find_text_rects(finding["text"], words)
            if rects:
                suggestions.append(Suggestion(
                    id=str(uuid.uuid4()),
                    text=finding["text"],
                    category=str(finding.get("category", "SensitiveContent")),
                    reasoning=finding.get("reasoning", ""),
                    context="",
                    page_num=page_num,
                    rects=rects,
                    source="ai"
                ))

    logger.info("Pipeline complete: %d suggestions generated", len(suggestions))

    return sorted(
        suggestions,
        key=lambda s: (s.page_num, s.rects[0].y0 if s.rects else 0)
    )
