import pytest
from unittest.mock import AsyncMock, MagicMock
from dependency_injector import providers
import app.containers.services as services_module
from app.containers.services import ServicesContainer
from app.containers.clients import ClientsContainer
from app.services.job_service import JobService
from app.services.redaction_service import RedactionService
from app.services.agent_service import AgentService
from app.services.workspace_service import WorkspaceService

@pytest.fixture
def test_config():
    """Shared test configuration for containers."""
    return {
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_deployment': 'gpt-4o',
        'azure_openai_api_version': '2024-02-01',
    }


def make_mock_oai():
    client = MagicMock()
    client.as_agent = MagicMock(return_value=MagicMock(create_session=MagicMock(), run=AsyncMock()))
    return client


def make_cosmos_account():
    jobs = MagicMock()
    workspaces = MagicMock()
    rules = MagicMock()
    exclusions = MagicMock()
    db = MagicMock()
    db.get_container_client.side_effect = lambda name: {
        "jobs": jobs,
        "workspaces": workspaces,
        "workspace_rules": rules,
        "workspace_exclusions": exclusions,
    }[name]
    cosmos = MagicMock()
    cosmos.get_database_client.return_value = db
    return cosmos, jobs, workspaces, rules, exclusions

def test_services_container_creates_factories(test_config):
    """Verify container creates service factories (not singletons)."""
    # Setup clients container with mocked clients
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)

    mock_cosmos, jobs, workspaces, rules, exclusions = make_cosmos_account()
    mock_blob = AsyncMock()
    mock_oai = make_mock_oai()

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
    assert job_service1.cosmos_container is jobs

def test_redaction_service_factory(test_config):
    """Verify RedactionService factory creates new instances."""
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)
    mock_cosmos, jobs, workspaces, rules, exclusions = make_cosmos_account()
    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: mock_cosmos)
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    clients_container.clients.oai_client.override(
        providers.Singleton(make_mock_oai)
    )

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    redaction1 = services_container.redaction_service()
    redaction2 = services_container.redaction_service()
    assert redaction1 is not redaction2
    assert isinstance(redaction1, RedactionService)
    assert redaction1.blob_client is not None

def test_agent_service_receives_job_service(test_config):
    """Verify AgentService receives JobService from container."""
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)
    mock_cosmos, jobs, workspaces, rules, exclusions = make_cosmos_account()
    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: mock_cosmos)
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    mock_oai = make_mock_oai()
    clients_container.clients.oai_client.override(
        providers.Singleton(lambda: mock_oai)
    )

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    agent = services_container.agent_service()
    assert isinstance(agent, AgentService)
    assert isinstance(agent.job_service, JobService)
    assert isinstance(agent.workspace_service, WorkspaceService)
    assert agent.knowledge_base is not None
    assert agent.oai_client is mock_oai


def test_workspace_service_factory(test_config):
    """Verify WorkspaceService factory creates new instances."""
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)
    mock_cosmos, jobs, workspaces, rules, exclusions = make_cosmos_account()
    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: mock_cosmos)
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    clients_container.clients.oai_client.override(
        providers.Singleton(make_mock_oai)
    )

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    workspace1 = services_container.workspace_service()
    workspace2 = services_container.workspace_service()
    assert workspace1 is not workspace2
    assert isinstance(workspace1, WorkspaceService)
    assert workspace1.workspaces_container is workspaces
    assert workspace1.rules_container is rules
    assert workspace1.exclusions_container is exclusions


def test_cosmos_failure_raises_not_silenced(test_config):
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)
    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: (_ for _ in ()).throw(RuntimeError("cosmos unavailable")))
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    clients_container.clients.oai_client.override(
        providers.Singleton(make_mock_oai)
    )

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    with pytest.raises(RuntimeError):
        services_container.job_service()


def test_in_memory_cosmos_client_removed():
    assert not hasattr(services_module, "_InMemoryCosmosClient")


def test_workspace_service_receives_three_containers(test_config):
    clients_container = ClientsContainer()
    clients_container.config.from_dict(test_config)
    mock_cosmos, jobs, workspaces, rules, exclusions = make_cosmos_account()
    clients_container.clients.cosmos_client.override(
        providers.Singleton(lambda: mock_cosmos)
    )
    clients_container.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    clients_container.clients.oai_client.override(
        providers.Singleton(make_mock_oai)
    )

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    workspace_service = services_container.workspace_service()

    params = workspace_service.__dict__
    assert "workspaces_container" in params
    assert "rules_container" in params
    assert "exclusions_container" in params
