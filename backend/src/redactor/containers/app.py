"""
Application-level dependency injection container.

Top-level container that composes all layers:
- ClientsContainer (infrastructure clients)
- ServicesContainer (business logic services)

This is the single entry point for dependency injection across the application.
All routes and services access dependencies through this container.
"""

from dependency_injector import containers, providers
from redactor.containers.clients import ClientsContainer
from redactor.containers.services import ServicesContainer


class AppContainer(containers.DeclarativeContainer):
    """
    Top-level application container.

    Composes both ClientsContainer and ServicesContainer.
    Single entry point for all dependency injection.

    Usage:
        container = AppContainer()
        container.config.from_dict({
            'cosmos_endpoint': '...',
            'azure_storage_account_url': '...',
            'azure_openai_endpoint': '...',
            'azure_openai_api_version': '...',
        })

        # Access services through container
        job_service = container.services.job_service()
    """

    # Configuration provider shared across all layers
    config = providers.Configuration()

    # Infrastructure layer (singleton clients)
    clients = providers.Container(ClientsContainer, config=config)

    # Business logic layer (service factories)
    services = providers.Container(ServicesContainer, clients=clients)
