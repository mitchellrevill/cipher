"""
Service layer dependency injection container.

Manages business logic services with factory pattern (new instance per call).
Services depend on infrastructure clients from ClientsContainer.
"""

from typing import Optional
from dependency_injector import containers, providers
from redactor.services.job_service import JobService
from redactor.services.redaction_service import RedactionService
from redactor.services.blob_service import BlobService
from redactor.services.agent_service import AgentService


def _create_job_service(cosmos_client):
    """Factory function to create JobService with cosmos client."""
    return JobService(cosmos_client=cosmos_client)


def _create_redaction_service(cosmos_client):
    """Factory function to create RedactionService with cosmos client."""
    return RedactionService(cosmos_client=cosmos_client)


def _create_blob_service(blob_client):
    """Factory function to create BlobService with blob client."""
    return BlobService(blob_client=blob_client)


def _create_agent_service(oai_client, job_service):
    """Factory function to create AgentService with oai client and job service."""
    return AgentService(
        oai_client=oai_client,
        job_service=job_service  # FIXED: Receives job_service from container's factory
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
        cosmos_client=providers.Callable(lambda c: c.clients.cosmos_client(), clients)
    )

    redaction_service = providers.Factory(
        _create_redaction_service,
        cosmos_client=providers.Callable(lambda c: c.clients.cosmos_client(), clients)
    )

    blob_service = providers.Factory(
        _create_blob_service,
        blob_client=providers.Callable(lambda c: c.clients.blob_client(), clients)
    )

    agent_service = providers.Factory(
        _create_agent_service,
        oai_client=providers.Callable(lambda c: c.clients.oai_client(), clients),
        job_service=job_service  # FIXED: Reuse container's job_service, not create new
    )
