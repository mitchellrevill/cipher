# backend/tests/test_containers_clients.py
import pytest
from unittest.mock import MagicMock, patch
from redactor.containers.clients import ClientsContainer

def test_clients_container_creates_singletons():
    """Verify container creates singleton clients on demand."""
    with patch('redactor.containers.clients.CosmosClient') as mock_cosmos, \
         patch('redactor.containers.clients.BlobServiceClient') as mock_blob, \
         patch('redactor.containers.clients.AsyncAzureOpenAI') as mock_oai, \
         patch('redactor.containers.clients.DefaultAzureCredential') as mock_cred:

        container = ClientsContainer()
        container.config.from_dict({
            'cosmos_endpoint': 'https://test.documents.azure.com:443/',
            'azure_storage_account_url': 'https://test.blob.core.windows.net',
            'azure_openai_endpoint': 'https://test.openai.azure.com/',
            'azure_openai_api_version': '2024-02-01',
        })

        # Get clients multiple times
        cosmos1 = container.clients.cosmos_client()
        cosmos2 = container.clients.cosmos_client()

        # Verify same instance (singleton)
        assert cosmos1 is cosmos2

def test_clients_container_requires_config():
    """Verify container requires config before access."""
    container = ClientsContainer()
    with pytest.raises(Exception):  # unset config
        container.clients.cosmos_client()
