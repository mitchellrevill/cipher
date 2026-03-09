# backend/tests/test_containers_services.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from dependency_injector import providers
from redactor.containers.services import ServicesContainer
from redactor.containers.clients import ClientsContainer
from redactor.services.job_service import JobService

def test_services_container_creates_factories():
    """Verify container creates service factories (not singletons)."""
    clients_container = ClientsContainer()
    clients_container.config.from_dict({
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_api_version': '2024-02-01',
    })

    # Mock the clients
    mock_cosmos = AsyncMock()
    mock_blob = AsyncMock()
    mock_oai = AsyncMock()

    clients_container.clients.cosmos_client.override(providers.Singleton(lambda: mock_cosmos))
    clients_container.clients.blob_client.override(providers.Singleton(lambda: mock_blob))
    clients_container.clients.oai_client.override(providers.Singleton(lambda: mock_oai))

    services_container = ServicesContainer()
    services_container.clients.override(clients_container)

    # Get service twice
    job_service1 = services_container.job_service()
    job_service2 = services_container.job_service()

    # Factory creates new instances (NOT the same)
    assert job_service1 is not job_service2
    assert isinstance(job_service1, JobService)
    assert isinstance(job_service2, JobService)
