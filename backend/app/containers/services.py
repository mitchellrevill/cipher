"""Service layer dependency injection container."""

import logging

from dependency_injector import containers, providers

from app.agent.knowledge_base import KnowledgeBase
from app.config import get_settings
from app.services.agent_service import AgentService
from app.services.job_service import JobService
from app.services.redaction_service import RedactionService
from app.services.rule_engine import RuleEngine
from app.services.session_service import SessionService
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)

def _get_jobs_container(c):
    settings = get_settings()
    cosmos_client = c.clients.cosmos_client()
    db = cosmos_client.get_database_client(settings.cosmos_db_name)
    return db.get_container_client("jobs")


def _get_workspace_container(c, name: str):
    settings = get_settings()
    cosmos_client = c.clients.cosmos_client()
    db = cosmos_client.get_database_client(settings.cosmos_db_name)
    return db.get_container_client(name)


def _create_job_service(cosmos_container, blob_client):
    return JobService(cosmos_container=cosmos_container, blob_client=blob_client)


def _create_redaction_service(blob_client):
    return RedactionService(blob_client=blob_client)


def _create_workspace_service(workspaces_container, rules_container, exclusions_container):
    return WorkspaceService(
        workspaces_container=workspaces_container,
        rules_container=rules_container,
        exclusions_container=exclusions_container,
    )


def _create_rule_engine():
    return RuleEngine()


def _create_agent_service(oai_client, job_service, workspace_service, redaction_service, rule_engine, knowledge_base, session_service):
    return AgentService(
        oai_client=oai_client,
        job_service=job_service,
        workspace_service=workspace_service,
        redaction_service=redaction_service,
        rule_engine=rule_engine,
        knowledge_base=knowledge_base,
        session_service=session_service,
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

    job_service = providers.Factory(
        _create_job_service,
        cosmos_container=providers.Callable(_get_jobs_container, clients),
        blob_client=providers.Callable(lambda c: c.clients.blob_client(), clients),
    )

    redaction_service = providers.Factory(
        _create_redaction_service,
        blob_client=providers.Callable(lambda c: c.clients.blob_client(), clients),
    )

    workspace_service = providers.Factory(
        _create_workspace_service,
        workspaces_container=providers.Callable(lambda c: _get_workspace_container(c, "workspaces"), clients),
        rules_container=providers.Callable(lambda c: _get_workspace_container(c, "workspace_rules"), clients),
        exclusions_container=providers.Callable(lambda c: _get_workspace_container(c, "workspace_exclusions"), clients),
    )

    session_service = providers.Factory(
        SessionService,
        blob_client=providers.Callable(lambda c: c.clients.blob_client(), clients),
    )

    knowledge_base = providers.Singleton(
        KnowledgeBase,
        workspace_service=workspace_service,
    )

    rule_engine = providers.Factory(_create_rule_engine)

    agent_service = providers.Factory(
        _create_agent_service,
        oai_client=providers.Callable(lambda c: c.clients.oai_client(), clients),
        job_service=job_service,
        workspace_service=workspace_service,
        redaction_service=redaction_service,
        rule_engine=rule_engine,
        knowledge_base=knowledge_base,
        session_service=session_service,
    )
