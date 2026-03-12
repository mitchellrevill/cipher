import pytest
from unittest.mock import AsyncMock, MagicMock
from dependency_injector import providers
from redactor.containers.services import ServicesContainer
from redactor.containers.clients import ClientsContainer
from redactor.services.job_service import JobService
from redactor.services.redaction_service import RedactionService
from redactor.services.agent_service import AgentService
from redactor.services.workspace_service import WorkspaceService

@pytest.fixture
def test_config():
    """Shared test configuration for containers."""
    return {
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_api_version': '2024-02-01',
    }

def test_services_container_creates_factories(test_config):
    """Verify container creates service factories (not singletons)."""
    # Setup clients container with mocked clients
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)

    mock_cosmos = AsyncMock()
    mock_blob = AsyncMock()
    mock_oai = AsyncMock()

    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: mock_cosmos)
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: mock_blob)
    )
    clients_container.clients.oai_client.override(
        providers.Singleton(lambda: mock_oai)
    )

    # Setup services container with mocked clients
    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    # Test JobService factory
    job_service1 = services_container.job_service()
    job_service2 = services_container.job_service()
    assert job_service1 is not job_service2
    assert isinstance(job_service1, JobService)
    assert isinstance(job_service2, JobService)

def test_redaction_service_factory(test_config):
    """Verify RedactionService factory creates new instances."""
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)
    mock_cosmos = AsyncMock()
    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: mock_cosmos)
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    clients_container.clients.oai_client.override(
        providers.Singleton(lambda: AsyncMock())
    )

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    redaction1 = services_container.redaction_service()
    redaction2 = services_container.redaction_service()
    assert redaction1 is not redaction2
    assert isinstance(redaction1, RedactionService)

def test_agent_service_receives_job_service(test_config):
    """Verify AgentService receives JobService from container."""
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)
    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    mock_oai = AsyncMock()
    clients_container.clients.oai_client.override(
        providers.Singleton(lambda: mock_oai)
    )

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    agent = services_container.agent_service()
    assert isinstance(agent, AgentService)
    assert isinstance(agent.job_service, JobService)
    assert isinstance(agent.workspace_service, WorkspaceService)
    assert agent.oai_client is mock_oai


def test_workspace_service_factory(test_config):
    """Verify WorkspaceService factory creates new instances."""
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)
    mock_cosmos = AsyncMock()
    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: mock_cosmos)
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    clients_container.clients.oai_client.override(
        providers.Singleton(lambda: AsyncMock())
    )

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    workspace1 = services_container.workspace_service()
    workspace2 = services_container.workspace_service()
    assert workspace1 is not workspace2
    assert isinstance(workspace1, WorkspaceService)
