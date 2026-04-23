# backend/tests/test_containers_app.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from dependency_injector import providers
from app.containers.app import AppContainer

def test_app_container_wires_both_layers():
    """Verify AppContainer composes both ClientsContainer and ServicesContainer."""
    container = AppContainer()
    container.config.from_dict({
        'cosmos_endpoint': 'https://test.documents.azure.com:443/',
        'azure_storage_account_url': 'https://test.blob.core.windows.net',
        'azure_openai_endpoint': 'https://test.openai.azure.com/',
        'azure_openai_api_version': '2024-02-01',
    })

    jobs_container = MagicMock()
    database = MagicMock()
    database.get_container_client.return_value = jobs_container
    cosmos_account = MagicMock()
    cosmos_account.get_database_client.return_value = database

    # Mock clients to avoid Azure authentication
    container.clients.clients.cosmos_client.override(
        providers.Singleton(lambda: cosmos_account)
    )
    container.clients.clients.blob_client.override(
        providers.Singleton(lambda: AsyncMock())
    )
    container.clients.clients.oai_client.override(
        providers.Singleton(lambda: AsyncMock())
    )

    # Access clients and services through app container
    assert hasattr(container, 'clients')
    assert hasattr(container, 'services')

    # Verify sub-containers are wired
    job_service = container.services.job_service()
    assert job_service is not None
