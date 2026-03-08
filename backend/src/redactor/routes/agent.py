from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from redactor.agent.redaction_agent import run_agent_turn
from redactor.routes.jobs import _jobs

router = APIRouter()

class ChatRequest(BaseModel):
    job_id: str
    message: str
    session_id: Optional[str] = None
    previous_response_id: Optional[str] = None

@router.post("/chat")
async def chat(request: ChatRequest):
    if request.job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    result = await run_agent_turn(
        job_id=request.job_id,
        user_message=request.message,
        previous_response_id=request.previous_response_id,
    )
    return result
