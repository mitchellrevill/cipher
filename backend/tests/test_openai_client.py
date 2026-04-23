import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.pipeline.openai_client import OpenAIRedactionClient

@pytest.fixture
def client():
    with patch("redactor.pipeline.openai_client.AsyncAzureOpenAI"):
        yield OpenAIRedactionClient(
            endpoint="https://test.openai.azure.com",
            key="key",
            deployment="gpt-4o",
            api_version="2024-02-01"
        )

@pytest.mark.asyncio
async def test_parse_instructions_returns_exceptions(client):
    mock_response = MagicMock()
    mock_response.output_text = '{"exceptions": ["Oliver Hughes"]}'
    client._client.responses.create = AsyncMock(return_value=mock_response)
    result = await client.parse_instructions("keep oliver hughes")
    assert "exceptions" in result
    assert "Oliver Hughes" in result["exceptions"]

@pytest.mark.asyncio
async def test_parse_instructions_returns_empty_for_blank_input(client):
    result = await client.parse_instructions("")
    assert result == {}

@pytest.mark.asyncio
async def test_get_contextual_redactions_returns_list(client):
    mock_response = MagicMock()
    mock_response.output_text = '{"redactions": [{"text": "bullying incident", "category": "SensitiveContent", "reasoning": "matches rule"}]}'
    client._client.responses.create = AsyncMock(return_value=mock_response)
    result = await client.get_contextual_redactions("page text here", "redact mentions of bullying")
    assert len(result) == 1
    assert result[0]["text"] == "bullying incident"

@pytest.mark.asyncio
async def test_get_contextual_redactions_returns_empty_on_api_error(client):
    client._client.responses.create = AsyncMock(side_effect=Exception("API error"))
    result = await client.get_contextual_redactions("text", "rule")
    assert result == []

@pytest.mark.asyncio
async def test_get_pii_via_llm_returns_entities(client):
    mock_response = MagicMock()
    mock_response.output_text = '{"entities": [{"text": "John Smith", "category": "Person", "offset": 0, "length": 10}]}'
    client._client.responses.create = AsyncMock(return_value=mock_response)
    result = await client.get_pii_via_llm("John Smith lives here")
    assert len(result) == 1
    assert result[0]["category"] == "Person"

@pytest.mark.asyncio
async def test_link_entities_returns_mapping(client):
    mock_response = MagicMock()
    mock_response.output_text = '{"John Smith": "John Smith", "14 March 2015": "John Smith"}'
    client._client.responses.create = AsyncMock(return_value=mock_response)
    entities = [{"text": "John Smith"}, {"text": "14 March 2015"}]
    result = await client.link_entities("John Smith was born on 14 March 2015.", entities)
    assert result["John Smith"] == "John Smith"
    assert result["14 March 2015"] == "John Smith"

@pytest.mark.asyncio
async def test_link_entities_returns_empty_for_no_entities(client):
    result = await client.link_entities("some text", [])
    assert result == {}
