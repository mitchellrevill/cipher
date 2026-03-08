from pydantic import BaseModel
from enum import Enum
from typing import Optional

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
    text: str
    category: str
    reasoning: str
    context: str
    page_num: int
    rects: list[RedactionRect]
    approved: bool = True
    source: str = "ai"  # "ai" | "manual" | "agent"

class Job(BaseModel):
    job_id: str
    status: JobStatus
    page_count: Optional[int] = None
    suggestions: list[Suggestion] = []
    error: Optional[str] = None

class AgentSession(BaseModel):
    session_id: str
    job_id: str
    previous_response_id: Optional[str] = None
