import pytest
from unittest.mock import MagicMock, patch
from redactor.pipeline.pii_service import PIIServiceClient

@pytest.fixture
def mock_pii_result():
    entity = MagicMock()
    entity.text = "John Smith"
    entity.category = "Person"
    entity.offset = 0
    entity.length = 10
    doc = MagicMock()
    doc.is_error = False
    doc.entities = [entity]
    return [doc]

def test_get_pii_returns_structured_entities(mock_pii_result):
    with patch("redactor.pipeline.pii_service.TextAnalyticsClient") as MockClient:
        MockClient.return_value.recognize_pii_entities.return_value = mock_pii_result
        client = PIIServiceClient(endpoint="https://test", key="key")
        result = client.get_pii("John Smith lives at 1 Main St.")
        assert len(result) == 1
        assert result[0]["text"] == "John Smith"
        assert result[0]["category"] == "Person"
        assert result[0]["offset"] == 0
        assert result[0]["length"] == 10

def test_get_pii_skips_error_documents():
    error_doc = MagicMock()
    error_doc.is_error = True
    with patch("redactor.pipeline.pii_service.TextAnalyticsClient") as MockClient:
        MockClient.return_value.recognize_pii_entities.return_value = [error_doc]
        client = PIIServiceClient(endpoint="https://test", key="key")
        result = client.get_pii("some text")
        assert result == []

def test_get_pii_returns_empty_on_exception():
    with patch("redactor.pipeline.pii_service.TextAnalyticsClient") as MockClient:
        MockClient.return_value.recognize_pii_entities.side_effect = Exception("API error")
        client = PIIServiceClient(endpoint="https://test", key="key")
        result = client.get_pii("some text")
        assert result == []
