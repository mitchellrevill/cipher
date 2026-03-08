from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redactor.config import get_settings
from redactor.routes import jobs, redactions, agent

app = FastAPI(title="AI Document Redactor")
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
