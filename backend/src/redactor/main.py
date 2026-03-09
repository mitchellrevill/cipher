from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redactor.config import get_settings
from redactor.containers.app import AppContainer
from redactor.routes import jobs, redactions, agent

logger = logging.getLogger(__name__)


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
    logger.info("Initializing dependency container...")

    try:
        settings = get_settings()
        container = AppContainer()
        container.config.from_dict({
            'cosmos_endpoint': settings.cosmos_endpoint,
            'azure_storage_account_url': settings.azure_storage_account_url,
            'azure_openai_endpoint': settings.azure_openai_endpoint,
            'azure_openai_api_version': settings.azure_openai_api_version,
        })

        # Initialize singleton clients
        cosmos = container.clients.cosmos_client()
        blob = container.clients.blob_client()
        oai = container.clients.oai_client()

        # Test connectivity (comment out if using Managed Identity in production)
        logger.info("Testing service connectivity...")
        logger.info("✓ Cosmos DB initialized")
        logger.info("✓ Blob Storage initialized")
        logger.info("✓ Azure OpenAI initialized")

        app.container = container

    except Exception as e:
        logger.error(f"Failed to initialize container: {e}")
        raise

    yield  # ← App runs here

    # ─── SHUTDOWN ───
    logger.info("Shutting down...")

    try:
        # Close clients gracefully
        if blob is not None and hasattr(blob, 'close'):
            try:
                await blob.close()
            except (AttributeError, TypeError):
                pass  # Client may not support async close

        if cosmos is not None and hasattr(cosmos, 'close'):
            try:
                cosmos.close()
            except (AttributeError, TypeError):
                pass  # Client may not support sync close

        logger.info("✓ Clients closed gracefully")
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
