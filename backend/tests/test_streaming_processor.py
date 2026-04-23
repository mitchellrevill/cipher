import pytest
from unittest.mock import AsyncMock, MagicMock
from app.pipeline.page_processor import StreamingPageProcessor, PageProcessingStage
from app.models import PageStatusEvent, SuggestionFoundEvent


@pytest.fixture
def mock_analysis():
    """Mock AnalyzeResult with 3 pages."""
    word1 = MagicMock()
    word1.content = "John"
    word1.polygon = [0.1, 0.1, 0.6, 0.1, 0.6, 0.3, 0.1, 0.3]

    word2 = MagicMock()
    word2.content = "Smith"
    word2.polygon = [0.6, 0.1, 1.1, 0.1, 1.1, 0.3, 0.6, 0.3]

    para1 = MagicMock()
    para1.content = "John Smith"
    para1.bounding_regions = [MagicMock(page_number=1)]
    para1.spans = [MagicMock(offset=0, length=10)]

    para2 = MagicMock()
    para2.content = "John Smith"
    para2.bounding_regions = [MagicMock(page_number=2)]
    para2.spans = [MagicMock(offset=100, length=10)]

    para3 = MagicMock()
    para3.content = "John Smith"
    para3.bounding_regions = [MagicMock(page_number=3)]
    para3.spans = [MagicMock(offset=200, length=10)]

    page1 = MagicMock()
    page1.page_number = 1
    page1.words = [word1, word2]
    page1.spans = [MagicMock(offset=0, length=100)]

    page2 = MagicMock()
    page2.page_number = 2
    page2.words = [word1, word2]
    page2.spans = [MagicMock(offset=100, length=100)]

    page3 = MagicMock()
    page3.page_number = 3
    page3.words = [word1, word2]
    page3.spans = [MagicMock(offset=200, length=100)]

    analysis = MagicMock()
    analysis.pages = [page1, page2, page3]
    analysis.paragraphs = [para1, para2, para3]
    analysis.content = "John Smith " * 30  # Enough content for 3 pages

    return analysis


@pytest.mark.asyncio
async def test_page_status_events(mock_analysis):
    """Test that page status events are emitted for each stage."""
    pii_client = AsyncMock()
    pii_client.get_pii = AsyncMock(return_value=[
        {"text": "John", "category": "Person", "offset": 0, "length": 4}
    ])

    oai_client = AsyncMock()
    config = MagicMock()
    config.enable_pii_service = True

    processor = StreamingPageProcessor(
        analysis=mock_analysis,
        pii_client=pii_client,
        oai_client=oai_client,
        config=config,
        batch_size=2,
    )

    events = []
    async for event in processor.process_pages_streaming(
        pii_exceptions=set(),
        sensitive_rule=None,
    ):
        events.append(event)

    # Check that we got status and suggestion events
    status_events = [e for e in events if isinstance(e, PageStatusEvent)]
    suggestion_events = [e for e in events if isinstance(e, SuggestionFoundEvent)]

    assert len(status_events) > 0, "Should have page status events"
    assert len(suggestion_events) > 0, "Should have suggestion events"


@pytest.mark.asyncio
async def test_suggestion_deduplication(mock_analysis):
    """Test that duplicate suggestions track all pages."""
    pii_client = AsyncMock()
    pii_client.get_pii = AsyncMock(return_value=[
        {"text": "John Smith", "category": "Person", "offset": 0, "length": 10}
    ])

    oai_client = AsyncMock()
    config = MagicMock()
    config.enable_pii_service = True

    processor = StreamingPageProcessor(
        analysis=mock_analysis,
        pii_client=pii_client,
        oai_client=oai_client,
        config=config,
    )

    events = []
    async for event in processor.process_pages_streaming(
        pii_exceptions=set(),
        sensitive_rule=None,
    ):
        events.append(event)

    suggestion_events = [e for e in events if isinstance(e, SuggestionFoundEvent)]
    assert len(suggestion_events) > 0
    # Final event should track all pages
    last_sugg = suggestion_events[-1]
    assert len(last_sugg.page_nums) == 3, f"Should track all 3 pages, got {len(last_sugg.page_nums)}"
