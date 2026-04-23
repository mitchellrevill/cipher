import pytest
from unittest.mock import patch
from app.containers.clients import ClientsContainer

@patch('redactor.containers.clients.CosmosClient')
@patch('redactor.containers.clients.AzureOpenAIResponsesClient')
@patch('redactor.containers.clients.DefaultAzureCredential')
def test_clients_container_creates_singletons(mock_cred, mock_oai, mock_cosmos):
    """Verify container creates singleton clients on demand."""
    container = ClientsContainer()
    container.config.from_dict({
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_deployment': 'gpt-4o',
        'azure_openai_api_version': '2024-02-01',
    })

    # Get clients multiple times
    cosmos1 = container.clients.cosmos_client()
    cosmos2 = container.clients.cosmos_client()

    # Verify same instance (singleton)
    assert cosmos1 is cosmos2

def test_clients_container_requires_cosmos_endpoint():
    """Verify container raises ValueError when cosmos endpoint is missing."""
    container = ClientsContainer()
    container.config.from_dict({
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_deployment': 'gpt-4o',
        'azure_openai_api_version': '2024-02-01',
    })

    with pytest.raises(ValueError, match="Cosmos endpoint"):
        container.clients.cosmos_client()

def test_clients_container_requires_storage_url():
    """Verify container raises ValueError when storage URL is missing."""
    container = ClientsContainer()
    container.config.from_dict({
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_deployment': 'gpt-4o',
        'azure_openai_api_version': '2024-02-01',
    })

    with pytest.raises(ValueError, match="Storage account URL"):
        container.clients.blob_client()

def test_clients_container_requires_oai_endpoint():
    """Verify container raises ValueError when OpenAI endpoint is missing."""
    container = ClientsContainer()
    container.config.from_dict({
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_api_version': '2024-02-01',
    })

    with pytest.raises(ValueError, match="Azure OpenAI endpoint"):
        container.clients.oai_client()

def test_clients_container_requires_oai_deployment():
    """Verify container raises ValueError when OpenAI deployment is missing."""
    container = ClientsContainer()
    container.config.from_dict({
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_api_version': '2024-02-01',
    })

    with pytest.raises(ValueError, match="Azure OpenAI deployment"):
        container.clients.oai_client()

@patch.dict('os.environ', {'AZURE_ENV': 'production'})
@patch('redactor.containers.clients.ManagedIdentityCredential')
def test_credential_uses_managed_identity_in_production(mock_managed_id):
    """Verify ManagedIdentityCredential is used in production environment."""
    container = ClientsContainer()
    container.config.from_dict({
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_deployment': 'gpt-4o',
        'azure_openai_api_version': '2024-02-01',
    })

    # Get credential (this will call ManagedIdentityCredential in production mode)
    cred = container.clients.credential()

    # Verify ManagedIdentityCredential was instantiated
    mock_managed_id.assert_called_once()

@patch.dict('os.environ', {}, clear=True)
@patch('redactor.containers.clients.DefaultAzureCredential')
def test_credential_uses_default_in_development(mock_default_cred):
    """Verify DefaultAzureCredential is used when AZURE_ENV is not 'production'."""
    container = ClientsContainer()
    container.config.from_dict({
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_deployment': 'gpt-4o',
        'azure_openai_api_version': '2024-02-01',
    })

    # Get credential (this will call DefaultAzureCredential in dev mode)
    cred = container.clients.credential()

    # Verify DefaultAzureCredential was instantiated
    mock_default_cred.assert_called_once()
