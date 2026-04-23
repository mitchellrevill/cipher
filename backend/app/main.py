from contextlib import asynccontextmanager
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import get_settings
from backend.app.containers.app import AppContainer
from backend.app.routes import agent, jobs, redactions
from backend.app.routes import workspaces

logger = logging.getLogger(__name__)


def _asyncio_exception_handler(loop, context):
    """Suppress benign SSL shutdown timeout warnings from Azure SDK (aiohttp transport)."""
    exc = context.get("exception")
    if exc is not None and "SSL shutdown timed out" in str(exc):
        return
    loop.default_exception_handler(context)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup:
    - Initialize dependency injection container
    - Create singleton clients (Cosmos, Blob, OpenAI)
    - Test connectivity to all services

    Shutdown:
    - Close all client connections gracefully
    """
    # ─── STARTUP ───
    asyncio.get_event_loop().set_exception_handler(_asyncio_exception_handler)
    logger.info("Initializing dependency container...")

    try:
        settings = get_settings()
        # log a couple of key values so we can see what actually loaded
        logger.info("Loaded settings:")
        logger.info(f"  azure_storage_account_url={settings.azure_storage_account_url!r}")
        logger.info(f"  azure_storage_account_key={'<redacted>' if settings.azure_storage_account_key else None}")
        logger.info(f"  cosmos_endpoint={settings.cosmos_endpoint!r}")
        logger.info(f"  azure_openai_endpoint={settings.azure_openai_endpoint!r}")
        logger.info(f"  azure_openai_key={'<redacted>' if settings.azure_openai_key else 'NOT SET'}")

        container = AppContainer()
        container.config.from_dict({
            'cosmos_endpoint': settings.cosmos_endpoint,
            'cosmos_key': settings.cosmos_key,
            'cosmos_db_name': settings.cosmos_db_name,
            'azure_storage_account_url': settings.azure_storage_account_url,
            'azure_storage_account_key': settings.azure_storage_account_key,
            'azure_openai_endpoint': settings.azure_openai_endpoint,
            'azure_openai_key': settings.azure_openai_key,
            'azure_openai_api_version': settings.azure_openai_api_version,
            'azure_openai_deployment': settings.azure_openai_deployment,
        })

        # Initialize singleton clients (from clients subcontainer)
        # Note: ClientsContainer exposes an inner `clients` subcontainer
        # so the providers live at `container.clients.clients`.
        # Creating some clients may trigger network calls (Cosmos SDK reads
        # account metadata on init). Wrap creation in try/except to avoid
        # failing app startup when credentials or RBAC are not available.
        # Defer creating clients at startup to avoid network/RBAC/credential
        # errors during import-time initialization. Clients will be created
        # lazily when first requested by services or routes.
        logger.info("Dependency container configured; deferring client creation until first use.")
        app.container = container

    except Exception as e:
        logger.error(f"Failed to initialize container: {e}")
        raise

    yield  # ← App runs here

    # ─── SHUTDOWN ───
    logger.info("Shutting down...")

    try:
        logger.info("✓ Shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Document Redactor",
    lifespan=lifespan
)

settings = get_settings()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(redactions.router, prefix="/api/jobs/{job_id}/redactions", tags=["redactions"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
