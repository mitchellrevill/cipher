import asyncio
from typing import AsyncGenerator
from app.models import PageStatusEvent, SuggestionFoundEvent, PageProcessingStage
from app.pipeline.doc_intelligence import DocIntelligenceClient
from app.pipeline.pii_service import PIIServiceClient
from app.pipeline.openai_client import OpenAIRedactionClient
from app.pipeline.fuzzy_matcher import find_text_rects
import logging
import uuid

logger = logging.getLogger(__name__)

class StreamingPageProcessor:
    """Process pages in parallel batches, emitting status and suggestion events."""

    def __init__(
        self,
        analysis,  # AnalyzeResult from Document Intelligence
        pii_client: PIIServiceClient | None,
        oai_client: OpenAIRedactionClient,
        config,
        batch_size: int = 4,
    ):
        self.analysis = analysis
        self.pii_client = pii_client
        self.oai_client = oai_client
        self.config = config
        self.batch_size = batch_size
        self.processed_suggestions = {}  # Track (text, category) -> page_nums

    async def emit_page_status(
        self,
        page_num: int,
        stage: PageProcessingStage,
        error_message: str | None = None,
    ) -> PageStatusEvent:
        """Create a page status event."""
        stage_labels = {
            PageProcessingStage.ANALYZING_LAYOUT: "Analyzing layout",
            PageProcessingStage.PII_DETECTION: "Running PII detection",
            PageProcessingStage.MATCHING_COORDINATES: "Matching to document",
            PageProcessingStage.COMPLETE: "Complete",
            PageProcessingStage.ERROR: "Error",
        }
        return PageStatusEvent(
            page_num=page_num,
            status=stage,
            stage_label=stage_labels[stage],
            error_message=error_message,
        )

    async def process_pages_streaming(
        self,
        pii_exceptions: set[str],
        sensitive_rule: str | None,
    ) -> AsyncGenerator[PageStatusEvent | SuggestionFoundEvent, None]:
        """
        Process pages in parallel batches, yielding status and suggestion events.
        """
        pages = self.analysis.pages or []
        paragraphs = self.analysis.paragraphs or []

        # Process in batches
        for batch_start in range(0, len(pages), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(pages))
            batch_pages = pages[batch_start:batch_end]

            # Create tasks for each page in the batch
            tasks = [
                self._process_single_page(
                    page,
                    paragraphs,
                    pii_exceptions,
                    sensitive_rule,
                )
                for page in batch_pages
            ]

            # Run batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Yield all events from batch
            for page_num, events in zip(
                range(batch_start, batch_end),
                batch_results,
            ):
                if isinstance(events, Exception):
                    logger.error(f"Page {page_num} failed: {events}")
                    yield await self.emit_page_status(
                        page_num,
                        PageProcessingStage.ERROR,
                    )
                else:
                    for event in events:
                        yield event

    async def _process_single_page(
        self,
        page,
        paragraphs,
        pii_exceptions: set[str],
        sensitive_rule: str | None,
    ) -> list[PageStatusEvent | SuggestionFoundEvent]:
        """Process a single page, returning all events for that page."""
        events = []
        page_num = page.page_number - 1

        try:
            # Stage 1: PII Detection
            yield_event = await self.emit_page_status(
                page_num,
                PageProcessingStage.PII_DETECTION,
            )
            events.append(yield_event)

            page_paras = [
                p for p in paragraphs
                if p.bounding_regions and p.bounding_regions[0].page_number == page.page_number
            ]

            # Get PII for this page
            pii_findings = []
            if self.config.enable_pii_service and self.pii_client:
                tasks = [self.pii_client.get_pii(p.content) for p in page_paras]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"PII task failed: {result}")
                    else:
                        pii_findings.extend(result)
            else:
                page_text = " ".join(p.content for p in page_paras)
                if page_text.strip():
                    pii_findings = await self.oai_client.get_pii_via_llm(page_text)

            # Stage 2: Matching Coordinates
            yield_event = await self.emit_page_status(
                page_num,
                PageProcessingStage.MATCHING_COORDINATES,
            )
            events.append(yield_event)

            # Get words for fuzzy matching
            words = list(page.words) if hasattr(page, 'words') else []

            # Process PII findings
            for entity in pii_findings:
                if entity.get("text", "").lower() in pii_exceptions:
                    continue

                rects = find_text_rects(entity["text"], words)
                if rects:
                    # Check if this suggestion already exists
                    key = (entity["text"], entity.get("category", "Unknown"))
                    if key in self.processed_suggestions:
                        # Update existing suggestion with new page
                        self.processed_suggestions[key]["page_nums"].append(page_num)
                    else:
                        # New suggestion
                        self.processed_suggestions[key] = {
                            "id": str(uuid.uuid4()),
                            "text": entity["text"],
                            "category": entity.get("category", "Unknown"),
                            "reasoning": f"Identified as {entity.get('category', 'PII')}",
                            "page_nums": [page_num],
                            "first_found_on": page_num,
                            "rects": [rect.model_dump() for rect in rects],
                        }

                    # Emit suggestion found event
                    sugg = self.processed_suggestions[key]
                    event = SuggestionFoundEvent(
                        id=sugg["id"],
                        text=sugg["text"],
                        category=sugg["category"],
                        reasoning=sugg["reasoning"],
                        page_nums=sugg["page_nums"],
                        first_found_on=sugg["first_found_on"],
                        rects=sugg["rects"],
                    )
                    events.append(event)

            # Stage 3: Contextual Redaction (if enabled)
            if sensitive_rule:
                page_text = self.analysis.content[
                    page.spans[0].offset: page.spans[0].offset + page.spans[0].length
                ] if page.spans else ""

                if page_text.strip():
                    contextual_findings = await self.oai_client.get_contextual_redactions(
                        page_text,
                        sensitive_rule,
                    )

                    for finding in contextual_findings:
                        if finding.get("text", "").lower() in pii_exceptions:
                            continue

                        rects = find_text_rects(finding["text"], words)
                        if rects:
                            key = (finding["text"], finding.get("category", "SensitiveContent"))
                            if key in self.processed_suggestions:
                                self.processed_suggestions[key]["page_nums"].append(page_num)
                            else:
                                self.processed_suggestions[key] = {
                                    "id": str(uuid.uuid4()),
                                    "text": finding["text"],
                                    "category": finding.get("category", "SensitiveContent"),
                                    "reasoning": finding.get("reasoning", ""),
                                    "page_nums": [page_num],
                                    "first_found_on": page_num,
                                }

                            sugg = self.processed_suggestions[key]
                            event = SuggestionFoundEvent(
                                id=sugg["id"],
                                text=sugg["text"],
                                category=sugg["category"],
                                reasoning=sugg["reasoning"],
                                page_nums=sugg["page_nums"],
                                first_found_on=sugg["first_found_on"],
                            )
                            events.append(event)

            # Stage 4: Complete
            yield_event = await self.emit_page_status(
                page_num,
                PageProcessingStage.COMPLETE,
            )
            events.append(yield_event)

        except Exception as e:
            logger.exception(f"Error processing page {page_num}")
            yield_event = await self.emit_page_status(
                page_num,
                PageProcessingStage.ERROR,
                error_message=str(e),
            )
            events.append(yield_event)

        return events
