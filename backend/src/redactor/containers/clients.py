import logging
from typing import Optional
from dependency_injector import containers, providers
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
from openai import AsyncAzureOpenAI
import os

AZURE_ENV_PRODUCTION = 'production'


def _validate_and_create_cosmos(
    url: Optional[str],
    credential,
    cosmos_key: Optional[str] = None,
) -> CosmosClient:
    """Validate and create Cosmos DB client.

    Auth priority: explicit key → managed-identity/DefaultAzureCredential.
    """
    if not url:
        raise ValueError("Cosmos endpoint URL required but not set in config")
    if cosmos_key:
        return CosmosClient(url=url, credential=cosmos_key)
    return CosmosClient(url=url, credential=credential)


def _validate_and_create_blob(
    account_url: Optional[str],
    credential,
    account_key: Optional[str] = None,
):
    """Validate and create Blob Storage client wrapper.

    Returns our BlobStorageClient wrapper (not the raw Azure SDK client).
    Auth priority: explicit account key (via connection string) → credential (managed identity).
    """
    from redactor.storage.blob import get_blob_storage
    
    if not account_url:
        raise ValueError("Azure Storage account URL required but not set in config")
    
    # get_blob_storage returns our BlobStorageClient wrapper
    return get_blob_storage(account_url, "redacted-jobs", account_key=account_key)


def _validate_and_create_oai(azure_endpoint: Optional[str], credential, api_version: Optional[str]) -> AsyncAzureOpenAI:
    """Validate and create Azure OpenAI client."""
    if not azure_endpoint:
        raise ValueError("Azure OpenAI endpoint required but not set in config")
    if not api_version:
        raise ValueError("Azure OpenAI API version required but not set in config")
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
        credential=credential,
        cosmos_key=config.cosmos_key,
    )

    blob_client = providers.Singleton(
        _validate_and_create_blob,
        account_url=config.azure_storage_account_url,
        credential=credential,
        account_key=config.azure_storage_account_key,
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
                if os.getenv('AZURE_ENV') == AZURE_ENV_PRODUCTION
                else DefaultAzureCredential()  # local dev: uses `az login`
    )

    # Sub-container for clients
    clients = providers.Container(
        ClientsSubcontainer,
        config=config,
        credential=credential
    )

    logger = providers.Singleton(logging.getLogger, __name__)
