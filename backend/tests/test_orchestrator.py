import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from redactor.pipeline.orchestrator import run_pipeline
from redactor.config import Settings

@pytest.fixture
def test_settings():
    return Settings(
        azure_doc_intel_endpoint="https://test",
        azure_doc_intel_key="key",
        azure_openai_endpoint="https://test.openai.azure.com",
        azure_openai_key="key",
        azure_language_endpoint="https://test",
        azure_language_key="key",
        enable_pii_service=False,
    )

@pytest.fixture
def mock_analysis():
    word = MagicMock()
    word.content = "John"
    word.span = MagicMock(offset=0, length=4)
    word.polygon = [0.1, 0.1, 0.6, 0.1, 0.6, 0.3, 0.1, 0.3]

    para = MagicMock()
    para.content = "John lives here."
    para.spans = [MagicMock(offset=0, length=16)]
    para.bounding_regions = [MagicMock(page_number=1)]

    page = MagicMock()
    page.page_number = 1
    page.words = [word]
    page.spans = [MagicMock(offset=0, length=16)]

    result = MagicMock()
    result.paragraphs = [para]
    result.pages = [page]
    result.content = "John lives here."
    return result

@pytest.mark.asyncio
async def test_run_pipeline_returns_suggestions(test_settings, mock_analysis):
    with patch("redactor.pipeline.orchestrator.DocIntelligenceClient") as MockDI, \
         patch("redactor.pipeline.orchestrator.OpenAIRedactionClient") as MockOAI, \
         patch("redactor.pipeline.orchestrator.PIIServiceClient"):

        MockDI.return_value.analyse = AsyncMock(return_value=mock_analysis)
        MockOAI.return_value.parse_instructions = AsyncMock(return_value={})
        MockOAI.return_value.get_pii_via_llm = AsyncMock(return_value=[
            {"text": "John", "category": "Person", "offset": 0, "length": 4}
        ])
        MockOAI.return_value.get_contextual_redactions = AsyncMock(return_value=[])
        MockOAI.return_value.link_entities = AsyncMock(return_value={})

        suggestions = await run_pipeline(b"pdf-bytes", "", test_settings)
        assert isinstance(suggestions, list)

@pytest.mark.asyncio
async def test_run_pipeline_uses_pii_service_when_enabled(test_settings, mock_analysis):
    test_settings.enable_pii_service = True
    with patch("redactor.pipeline.orchestrator.DocIntelligenceClient") as MockDI, \
         patch("redactor.pipeline.orchestrator.OpenAIRedactionClient") as MockOAI, \
         patch("redactor.pipeline.orchestrator.PIIServiceClient") as MockPII:

        MockDI.return_value.analyse = AsyncMock(return_value=mock_analysis)
        MockOAI.return_value.parse_instructions = AsyncMock(return_value={})
        MockOAI.return_value.get_contextual_redactions = AsyncMock(return_value=[])
        MockPII.return_value.get_pii = AsyncMock(return_value=[
            {"text": "John", "category": "Person", "offset": 0, "length": 4}
        ])

        await run_pipeline(b"pdf-bytes", "", test_settings)
        MockPII.return_value.get_pii.assert_called()

@pytest.mark.asyncio
async def test_run_pipeline_returns_empty_when_no_findings(test_settings, mock_analysis):
    with patch("redactor.pipeline.orchestrator.DocIntelligenceClient") as MockDI, \
         patch("redactor.pipeline.orchestrator.OpenAIRedactionClient") as MockOAI, \
         patch("redactor.pipeline.orchestrator.PIIServiceClient"):

        MockDI.return_value.analyse = AsyncMock(return_value=mock_analysis)
        MockOAI.return_value.parse_instructions = AsyncMock(return_value={})
        MockOAI.return_value.get_pii_via_llm = AsyncMock(return_value=[])
        MockOAI.return_value.get_contextual_redactions = AsyncMock(return_value=[])

        suggestions = await run_pipeline(b"pdf-bytes", "", test_settings)
        assert suggestions == []
