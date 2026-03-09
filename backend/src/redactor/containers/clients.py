import logging
from dependency_injector import containers, providers
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
from openai import AsyncAzureOpenAI
import os


def _validate_and_create_cosmos(url, credential):
    """Create CosmosClient with config validation."""
    if url is None:
        raise ValueError("cosmos_endpoint config is required but not set")
    return CosmosClient(url=url, credential=credential)


def _validate_and_create_blob(account_url, credential):
    """Create BlobServiceClient with config validation."""
    if account_url is None:
        raise ValueError("azure_storage_account_url config is required but not set")
    return BlobServiceClient(account_url=account_url, credential=credential)


def _validate_and_create_oai(azure_endpoint, credential, api_version):
    """Create AsyncAzureOpenAI with config validation."""
    if azure_endpoint is None:
        raise ValueError("azure_openai_endpoint config is required but not set")
    if api_version is None:
        raise ValueError("azure_openai_api_version config is required but not set")
    return AsyncAzureOpenAI(
        azure_endpoint=azure_endpoint,
        credential=credential,
        api_version=api_version
    )


class ClientsSubcontainer(containers.DeclarativeContainer):
    """Sub-container for Azure clients."""

    config = providers.Configuration()
    credential = providers.Dependency()

    cosmos_client = providers.Singleton(
        _validate_and_create_cosmos,
        url=config.cosmos_endpoint,
        credential=credential
    )

    blob_client = providers.Singleton(
        _validate_and_create_blob,
        account_url=config.azure_storage_account_url,
        credential=credential
    )

    oai_client = providers.Singleton(
        _validate_and_create_oai,
        azure_endpoint=config.azure_openai_endpoint,
        credential=credential,
        api_version=config.azure_openai_api_version
    )


class ClientsContainer(containers.DeclarativeContainer):
    """
    Infrastructure client container.

    Manages singleton instances of:
    - Cosmos DB client
    - Azure Blob Storage client
    - Azure OpenAI client
    - Credentials (Managed Identity or DefaultAzureCredential)

    All clients are created once at app startup and reused throughout the lifetime.
    """

    config = providers.Configuration()

    # Single credential object, reused for all Azure services
    credential = providers.Singleton(
        lambda: ManagedIdentityCredential()
                if os.getenv('AZURE_ENV') == 'production'
                else DefaultAzureCredential()  # local dev: uses `az login`
    )

    # Sub-container for clients
    clients = providers.Container(
        ClientsSubcontainer,
        config=config,
        credential=credential
    )

    logger = providers.Singleton(logging.getLogger, __name__)
