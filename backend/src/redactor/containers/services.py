from typing import Optional
from dependency_injector import containers, providers
from redactor.services.job_service import JobService
from redactor.services.redaction_service import RedactionService
from redactor.services.blob_service import BlobService
from redactor.services.agent_service import AgentService


def _create_job_service(clients_container):
    """Factory function to create JobService from clients container."""
    return JobService(cosmos_client=clients_container.clients.cosmos_client())


def _create_redaction_service(clients_container):
    """Factory function to create RedactionService from clients container."""
    return RedactionService(cosmos_client=clients_container.clients.cosmos_client())


def _create_blob_service(clients_container):
    """Factory function to create BlobService from clients container."""
    return BlobService(blob_client=clients_container.clients.blob_client())


def _create_agent_service(clients_container):
    """Factory function to create AgentService from clients container."""
    job_service = JobService(cosmos_client=clients_container.clients.cosmos_client())
    return AgentService(
        oai_client=clients_container.clients.oai_client(),
        job_service=job_service
    )


class ServicesContainer(containers.DeclarativeContainer):
    """
    Business logic service container.

    Manages service factories that depend on infrastructure clients.
    Services are created per-request (factories, not singletons).
    Each call to a service provider creates a new instance.
    """

    # Dependency: will be injected with ClientsContainer
    clients = providers.Dependency()

    # Services are factories (create new instance per call)
    job_service = providers.Factory(
        _create_job_service,
        clients_container=clients
    )

    redaction_service = providers.Factory(
        _create_redaction_service,
        clients_container=clients
    )

    blob_service = providers.Factory(
        _create_blob_service,
        clients_container=clients
    )

    agent_service = providers.Factory(
        _create_agent_service,
        clients_container=clients
    )
