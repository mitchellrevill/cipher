"""
AI agent service for conversational redaction assistance.

Handles chat sessions and agent turn execution with Azure OpenAI.
Manages conversation history for context-aware responses.
"""

from typing import Optional, Dict, List
from datetime import datetime
import uuid
from openai import AsyncAzureOpenAI
from redactor.services.job_service import JobService


class AgentService:
    """
    AI agent service for conversational assistance with document redaction.

    Manages chat sessions and OpenAI turn execution.
    Provides context-aware responses about redaction decisions.
    """

    def __init__(self, oai_client: AsyncAzureOpenAI, job_service: JobService):
        """
        Initialize AgentService.

        Args:
            oai_client: Azure OpenAI async client
            job_service: JobService for accessing job context
        """
        self.oai_client = oai_client
        self.job_service = job_service
        self.sessions = {}  # In-memory session cache; will use Cosmos DB (Task 9)

    async def create_session(self, job_id: str) -> Dict:
        """
        Create a new chat session for a job.

        Args:
            job_id: Job identifier

        Returns:
            Chat session dict with id, job_id, created_at, messages
        """
        session_id = str(uuid.uuid4())
        session = {
            "id": session_id,
            "job_id": job_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_response_id": None,
            "messages": []
        }
        self.sessions[session_id] = session
        return session

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Get a chat session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session dict or None if not found
        """
        return self.sessions.get(session_id)

    async def save_message(self, session_id: str, role: str, text: str):
        """
        Save a message to the session.

        Args:
            session_id: Session identifier
            role: "user" or "assistant"
            text: Message text
        """
        if session_id in self.sessions:
            message = {
                "role": role,
                "text": text,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.sessions[session_id]["messages"].append(message)

    async def run_turn(
        self,
        job_id: str,
        message: str,
        previous_response_id: Optional[str] = None
    ) -> Dict:
        """
        Run an agent turn with Azure OpenAI.

        Sends message to OpenAI with job context, receives response.

        Args:
            job_id: Job identifier for context
            message: User message
            previous_response_id: Optional ID of previous response for continuation

        Returns:
            Dict with text, response_id, and optional tool_calls
        """
        try:
            # Get job context for system prompt
            job = await self.job_service.get_job(job_id)

            system_prompt = (
                f"You are a helpful assistant assisting with document redaction. "
                f"The user is working with document: {job.filename if job else 'unknown'}. "
                f"Provide clear, concise answers about redaction decisions and suggestions."
            )

            # Call OpenAI
            response = await self.oai_client.chat.completions.create(
                model="gpt-4",  # Will be set from config
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=500
            )

            # Extract response
            assistant_message = response.choices[0].message.content
            response_id = str(uuid.uuid4())

            return {
                "text": assistant_message,
                "response_id": response_id,
                "tool_calls": []
            }

        except Exception as e:
            return {
                "text": f"Error processing request: {str(e)}",
                "response_id": None,
                "tool_calls": []
            }
