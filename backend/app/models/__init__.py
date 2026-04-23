from pydantic import BaseModel, Field
from enum import Enum
from typing import Literal, Optional
from datetime import datetime
from app.models.workspace import Workspace, WorkspaceRule, WorkspaceExclusion

# Existing models from original models.py

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"

class RedactionRect(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

class Suggestion(BaseModel):
    id: str
    job_id: str
    text: str
    category: str
    reasoning: str
    context: str
    page_num: int
    rects: list[RedactionRect]
    approved: bool = False
    source: Literal["ai", "manual", "agent"] = "ai"
    created_at: datetime
    updated_at: Optional[datetime] = None

class Job(BaseModel):
    job_id: str
    status: JobStatus
    filename: Optional[str] = None
    page_count: int = 0
    suggestions: list[Suggestion] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_id: Optional[str] = None
    instructions: Optional[str] = None
    workspace_id: Optional[str] = None
    blob_path: Optional[str] = None
    output_blob_path: Optional[str] = None

# New streaming models
from app.models.streaming import (
    PageProcessingStage,
    PageStatusEvent,
    SuggestionFoundEvent,
    StreamingEventPayload,
)

__all__ = [
    "JobStatus",
    "RedactionRect",
    "Suggestion",
    "Job",
    "Workspace",
    "WorkspaceRule",
    "WorkspaceExclusion",
    "PageProcessingStage",
    "PageStatusEvent",
    "SuggestionFoundEvent",
    "StreamingEventPayload",
]
