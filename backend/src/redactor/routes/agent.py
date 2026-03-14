import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Annotated
from redactor.services.agent_service import AgentService

router = APIRouter()

class ChatRequest(BaseModel):
    job_id: str
    message: str
    workspace_id: Optional[str] = None
    session_id: Optional[str] = None  # reserved for future multi-session DB persistence


async def get_agent_service(request: Request) -> AgentService:
    """Get AgentService from app container."""
    return request.app.container.services.agent_service()


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
        if request.workspace_id is None:
            session_id = await agent_service.create_session(request.job_id)
        else:
            session_id = await agent_service.create_session(request.job_id, workspace_id=request.workspace_id)
    else:
        session = await agent_service.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = request.session_id

    # Get agent response
    run_turn_kwargs = {
        "session_id": session_id,
        "message": request.message,
    }
    if request.workspace_id is not None:
        run_turn_kwargs["workspace_id"] = request.workspace_id

    response = await agent_service.run_turn(**run_turn_kwargs)

    return {
        "session_id": session_id,
        "response": response["text"],
    }


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)] = None,
):
    """Stream chat responses and tool events from the AI assistant."""
    job = await agent_service.job_service.get_job(request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not request.session_id:
        if request.workspace_id is None:
            session_id = await agent_service.create_session(request.job_id)
        else:
            session_id = await agent_service.create_session(request.job_id, workspace_id=request.workspace_id)
    else:
        session = await agent_service.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = request.session_id

    async def event_generator():
        async for event in agent_service.run_turn_stream(
            session_id=session_id,
            message=request.message,
            workspace_id=request.workspace_id,
        ):
            event_name = event.get("type", "message")
            yield f"event: {event_name}\n"
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
