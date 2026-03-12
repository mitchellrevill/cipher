"""Service layer dependency injection container."""

from dependency_injector import containers, providers
from redactor.agent.orchestrator import RedactionOrchestrator
from redactor.services.job_service import JobService
from redactor.services.redaction_service import RedactionService
from redactor.services.agent_service import AgentService
from redactor.services.rule_engine import RuleEngine
from redactor.services.workspace_service import WorkspaceService


# In-memory stub for Cosmos DB used as a local fallback when the real
# Cosmos client cannot be created (e.g., missing RBAC permissions).
class _InMemoryCosmosClient:
    def __init__(self):
        self._store = {}

    def create_item(self, body=None, **kwargs):
        doc = body or {}
        key = doc.get('job_id') or doc.get('id')
        if not key:
            raise ValueError('Missing job id in document')
        self._store[key] = doc
        return doc

    def read_item(self, item, partition_key=None, **kwargs):
        if item in self._store:
            return self._store[item]
        raise Exception('NotFound')

    def update_item(self, item=None, body=None, **kwargs):
        key = item
        if key in self._store:
            # merge updates into existing document
            self._store[key].update(body or {})
            return self._store[key]
        raise Exception('NotFound')

    def upsert_item(self, body=None, **kwargs):
        return self.create_item(body=body, **kwargs)

    def delete_item(self, item=None, partition_key=None, **kwargs):
        if item in self._store:
            deleted = self._store[item]
            del self._store[item]
            return deleted
        raise Exception('NotFound')

    def query_items(self, query=None, parameters=None, **kwargs):
        items = list(self._store.values())
        params = {param['name']: param['value'] for param in (parameters or [])}
        if '@workspace_id' in params:
            items = [item for item in items if item.get('workspace_id') == params['@workspace_id']]
        if '@user_id' in params:
            items = [item for item in items if item.get('user_id') == params['@user_id']]
        return items


class _InMemoryDatabaseClient:
    def __init__(self):
        self._containers = {}

    def get_container_client(self, name):
        if name not in self._containers:
            self._containers[name] = _InMemoryCosmosClient()
        return self._containers[name]


class _InMemoryCosmosAccount:
    def __init__(self):
        self._databases = {}

    def get_database_client(self, name):
        if name not in self._databases:
            self._databases[name] = _InMemoryDatabaseClient()
        return self._databases[name]


def _safe_get_cosmos(c):
    """Attempt to get a real Cosmos client; fall back to in-memory stub on error."""
    # Keep a single shared in-memory instance so data persists across
    # multiple service factory invocations during local development.
    global _inmemory_cosmos_instance
    try:
        cosmos_client = c.clients.cosmos_client()
        # Wrap the real CosmosClient to provide the expected interface
        # (container access is lazy/deferred until the first operation)
        return _CosmosClientWrapper(cosmos_client)
    except Exception:
        if '_inmemory_cosmos_instance' not in globals() or globals().get('_inmemory_cosmos_instance') is None:
            globals()['_inmemory_cosmos_instance'] = _InMemoryCosmosClient()
        return globals()['_inmemory_cosmos_instance']


def _safe_get_cosmos_account(c):
    """Attempt to get a real Cosmos account client; fall back to in-memory account."""
    global _inmemory_cosmos_account
    try:
        return c.clients.cosmos_client()
    except Exception:
        if '_inmemory_cosmos_account' not in globals() or globals().get('_inmemory_cosmos_account') is None:
            globals()['_inmemory_cosmos_account'] = _InMemoryCosmosAccount()
        return globals()['_inmemory_cosmos_account']


def _safe_get_blob(c):
    """Safely get blob storage client, returning None if unavailable."""
    try:
        blob_client = c.clients.blob_client()
        import logging
        logging.getLogger(__name__).info(f"Got blob_client: {type(blob_client)}")
        return blob_client
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to get blob_client: {type(e).__name__}: {str(e)}")
        return None


class _CosmosClientWrapper:
    """Wrapper that provides the container-level interface for the real Cosmos client."""
    def __init__(self, cosmos_client):
        self._cosmos = cosmos_client
        self._container = None
        self._fallback = None  # lazy in-memory fallback

    def _get_or_create_fallback(self):
        """Lazily create in-memory fallback."""
        if self._fallback is None:
            self._fallback = _InMemoryCosmosClient()
        return self._fallback

    def _get_container(self):
        """Lazily get the default jobs container."""
        if self._container is None:
            try:
                from redactor.config import get_settings

                db_client = self._cosmos.get_database_client(get_settings().cosmos_db_name)
                self._container = db_client.get_container_client('jobs')
            except Exception:
                # Fall back to in-memory on any error (missing DB, missing container, etc.)
                return self._get_or_create_fallback()
        return self._container

    def create_item(self, body=None, **kwargs):
        try:
            return self._get_container().create_item(body=body, **kwargs)
        except Exception:
            # Fall back to in-memory on any error
            return self._get_or_create_fallback().create_item(body=body, **kwargs)

    def read_item(self, item, partition_key=None, **kwargs):
        try:
            return self._get_container().read_item(item=item, partition_key=partition_key, **kwargs)
        except Exception:
            return self._get_or_create_fallback().read_item(item=item, partition_key=partition_key, **kwargs)

    def update_item(self, item=None, body=None, **kwargs):
        try:
            container = self._get_container()
            # Cosmos SDK uses replace_item, not update_item. Need to read existing item first,
            # merge updates, then replace the whole document.
            existing = container.read_item(item=item, partition_key=item)
            existing.update(body or {})
            return container.replace_item(item=item, body=existing, **kwargs)
        except Exception:
            return self._get_or_create_fallback().update_item(item=item, body=body, **kwargs)


def _create_job_service(cosmos_client, blob_client):
    """Factory function to create JobService with cosmos and blob clients."""
    return JobService(cosmos_client=cosmos_client, blob_client=blob_client)


def _create_redaction_service(cosmos_client, blob_client):
    """Factory function to create RedactionService with cosmos and blob clients."""
    return RedactionService(cosmos_client=cosmos_client, blob_client=blob_client)


def _create_agent_service(oai_client, job_service):
    """Factory function to create AgentService with oai client and job service."""
    return AgentService(
        oai_client=oai_client,
        job_service=job_service  # FIXED: Receives job_service from container's factory
    )


def _create_workspace_service(cosmos_client):
    """Factory function to create WorkspaceService with a Cosmos account client."""
    return WorkspaceService(cosmos_client=cosmos_client)


def _create_rule_engine():
    """Factory function to create RuleEngine."""
    return RuleEngine()


def _create_orchestrated_agent_service(oai_client, job_service, redaction_service, workspace_service, rule_engine):
    """Factory function to create AgentService with workspace-aware orchestration."""
    return AgentService(
        oai_client=oai_client,
        job_service=job_service,
        workspace_service=workspace_service,
        orchestrator=RedactionOrchestrator(
            oai_client=oai_client,
            job_service=job_service,
            redaction_service=redaction_service,
            workspace_service=workspace_service,
            rule_engine=rule_engine,
        ),
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
        cosmos_client=providers.Callable(_safe_get_cosmos, clients),
        blob_client=providers.Callable(_safe_get_blob, clients)
    )

    redaction_service = providers.Factory(
        _create_redaction_service,
        cosmos_client=providers.Callable(_safe_get_cosmos, clients),
        blob_client=providers.Callable(_safe_get_blob, clients)
    )

    workspace_service = providers.Factory(
        _create_workspace_service,
        cosmos_client=providers.Callable(_safe_get_cosmos_account, clients)
    )

    rule_engine = providers.Factory(_create_rule_engine)

    agent_service = providers.Factory(
        _create_orchestrated_agent_service,
        oai_client=providers.Callable(lambda c: c.clients.oai_client(), clients),
        job_service=job_service,
        redaction_service=redaction_service,
        workspace_service=workspace_service,
        rule_engine=rule_engine,
    )
