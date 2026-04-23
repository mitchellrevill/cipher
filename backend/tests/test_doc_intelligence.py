import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.pipeline.doc_intelligence import DocIntelligenceClient

@pytest.fixture
def mock_analyse_result():
    word = MagicMock()
    word.content = "John"
    word.span = MagicMock(offset=0, length=4)
    word.polygon = [0.1, 0.1, 0.6, 0.1, 0.6, 0.3, 0.1, 0.3]

    para = MagicMock()
    para.content = "John Smith lives here."
    para.spans = [MagicMock(offset=0, length=22)]
    para.bounding_regions = [MagicMock(page_number=1)]

    page = MagicMock()
    page.page_number = 1
    page.words = [word]
    page.spans = [MagicMock(offset=0, length=22)]

    result = MagicMock()
    result.paragraphs = [para]
    result.pages = [page]
    result.content = "John Smith lives here."
    return result

@pytest.mark.asyncio
async def test_analyse_calls_begin_analyse_document(mock_analyse_result):
    with patch("redactor.pipeline.doc_intelligence._AsyncClient") as MockClient:
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        mock_poller = AsyncMock()
        mock_poller.result = AsyncMock(return_value=mock_analyse_result)
        mock_client_instance.begin_analyze_document = AsyncMock(return_value=mock_poller)

        client = DocIntelligenceClient(
            endpoint="https://test.cognitiveservices.azure.com",
            key="test-key"
        )
        result = await client.analyse(b"pdf-bytes")
        assert result.paragraphs is not None
        assert result.pages is not None
        mock_client_instance.begin_analyze_document.assert_called_once()

@pytest.mark.asyncio
async def test_analyse_uses_prebuilt_layout_model(mock_analyse_result):
    with patch("redactor.pipeline.doc_intelligence._AsyncClient") as MockClient:
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_poller = AsyncMock()
        mock_poller.result = AsyncMock(return_value=mock_analyse_result)
        mock_client_instance.begin_analyze_document = AsyncMock(return_value=mock_poller)

        client = DocIntelligenceClient(endpoint="https://test", key="key")
        await client.analyse(b"bytes")
        call_args = mock_client_instance.begin_analyze_document.call_args
        assert call_args[0][0] == "prebuilt-layout"
