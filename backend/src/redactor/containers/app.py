"""Application dependency injection container."""

from dependency_injector import containers, providers
from redactor.storage.blob import BlobStorageClient
from redactor.services.job_service import JobService
from redactor.services.redaction_service import RedactionService
from redactor.services.agent_service import AgentService


class AppContainer(containers.DeclarativeContainer):
    """
    Application dependency injection container.

    Manages singleton initialization and lifecycle of all application clients:
    - Cosmos DB client
    - Blob Storage client
    - Azure OpenAI client

    And application services:
    - JobService for job lifecycle management
    - RedactionService for document redaction
    - AgentService for conversational AI assistance
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

    # Application services
    job_service = providers.Factory(
        JobService,
        cosmos_client=cosmos_client,
    )

    redaction_service = providers.Factory(
        RedactionService,
        cosmos_client=cosmos_client,
    )

    agent_service = providers.Factory(
        AgentService,
        oai_client=oai_client,
        job_service=job_service,
    )
