from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Annotated
from redactor.services.agent_service import AgentService

router = APIRouter()

class ChatRequest(BaseModel):
    job_id: str
    message: str
    session_id: Optional[str] = None  # reserved for future multi-session DB persistence
    previous_response_id: Optional[str] = None


async def get_agent_service(request: Request) -> AgentService:
    """Get AgentService from app container."""
    return request.app.container.agent_service()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)] = None
):
    """Chat with AI assistant about document redaction."""

    # Verify job exists by checking if we can get job context from service
    job = await agent_service.job_service.get_job(request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create or get session
    if not request.session_id:
        session = await agent_service.create_session(request.job_id)
        session_id = session["id"]
    else:
        session = await agent_service.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = request.session_id

    # Save user message
    await agent_service.save_message(session_id, "user", request.message)

    # Get agent response
    response = await agent_service.run_turn(
        job_id=request.job_id,
        message=request.message,
        previous_response_id=request.previous_response_id
    )

    # Save assistant message
    await agent_service.save_message(session_id, "assistant", response["text"])

    return {
        "session_id": session_id,
        "response": response["text"],
        "response_id": response["response_id"]
    }
