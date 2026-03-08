from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redactor.config import get_settings
from redactor.storage.blob import BlobStorageClient
from redactor.routes import jobs, redactions, agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.blob_client = BlobStorageClient(
        settings.azure_storage_account_url, settings.azure_storage_container
    )
    yield
    await app.state.blob_client._container_client.close()


app = FastAPI(title="AI Document Redactor", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(redactions.router, prefix="/api/jobs/{job_id}/redactions", tags=["redactions"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
