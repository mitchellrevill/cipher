"""Application dependency injection container."""

from dependency_injector import containers, providers
from redactor.storage.blob import BlobStorageClient


class AppContainer(containers.DeclarativeContainer):
    """
    Application dependency injection container.

    Manages singleton initialization and lifecycle of all application clients:
    - Cosmos DB client
    - Blob Storage client
    - Azure OpenAI client
    """

    config = providers.Configuration()

    # Clients services
    blob_client = providers.Singleton(
        BlobStorageClient,
        account_url=config.azure_storage_account_url,
        container_name=config.azure_storage_container,
    )

    cosmos_client = providers.Factory(
        lambda: None,  # Placeholder - Cosmos client to be implemented
    )

    oai_client = providers.Factory(
        lambda: None,  # Placeholder - OpenAI client to be implemented
    )
