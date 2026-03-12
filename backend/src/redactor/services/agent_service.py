"""AI agent service for conversational redaction assistance."""

from typing import Optional, Dict
from datetime import datetime
import uuid
from openai import AsyncAzureOpenAI

from redactor.agent.orchestrator import RedactionOrchestrator
from redactor.config import get_settings
from redactor.services.job_service import JobService
from redactor.services.workspace_service import WorkspaceService


class AgentService:
    """
    AI agent service for conversational assistance with document redaction.

    Manages chat sessions and OpenAI turn execution.
    Provides context-aware responses about redaction decisions.
    """

    def __init__(
        self,
        oai_client: AsyncAzureOpenAI,
        job_service: JobService,
        workspace_service: WorkspaceService | None = None,
        orchestrator: RedactionOrchestrator | None = None,
    ):
        """
        Initialize AgentService.

        Args:
            oai_client: Azure OpenAI async client
            job_service: JobService for accessing job context
        """
        self.oai_client = oai_client
        self.job_service = job_service
        self.workspace_service = workspace_service
        self.orchestrator = orchestrator
        self.settings = get_settings()
        self.sessions = {}  # In-memory session cache; will use Cosmos DB (Task 9)

    async def create_session(self, job_id: str, workspace_id: Optional[str] = None) -> Dict:
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
            "workspace_id": workspace_id,
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
        previous_response_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        session_id: Optional[str] = None,
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
            job = await self.job_service.get_job(job_id)
            active_workspace_id = workspace_id or self._get_session_workspace_id(session_id)
            workspace_context = await self._load_workspace_context(active_workspace_id)
            session_messages = self.sessions.get(session_id, {}).get("messages", []) if session_id else []

            if self.orchestrator is not None:
                response = await self.orchestrator.run_turn(
                    user_message=message,
                    workspace_context=workspace_context,
                    session_messages=session_messages,
                )
                response.setdefault("response_id", str(uuid.uuid4()))
                response.setdefault("tool_calls", [])
                response.setdefault("directives", [])
                return response

            response = await self.oai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": self._build_system_prompt(job, workspace_context)},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=500
            )

            assistant_message = response.choices[0].message.content
            response_id = str(uuid.uuid4())

            return {
                "text": assistant_message,
                "response_id": response_id,
                "tool_calls": [],
                "directives": [],
            }

        except Exception as e:
            return {
                "text": f"Error processing request: {str(e)}",
                "response_id": None,
                "tool_calls": [],
                "directives": [],
            }

    async def _load_workspace_context(self, workspace_id: Optional[str]) -> Optional[Dict]:
        if not workspace_id or self.workspace_service is None:
            return None

        try:
            return await self.workspace_service.get_workspace_state(workspace_id)
        except Exception:
            return None

    def _get_session_workspace_id(self, session_id: Optional[str]) -> Optional[str]:
        if not session_id:
            return None
        session = self.sessions.get(session_id)
        if not session:
            return None
        return session.get("workspace_id")

    def _build_system_prompt(self, job, workspace_context: Optional[Dict]) -> str:
        prompt = (
            f"You are a helpful assistant assisting with document redaction. "
            f"The user is working with document: {job.filename if job else 'unknown'}. "
            f"Provide clear, concise answers about redaction decisions and suggestions."
        )
        if workspace_context:
            prompt += (
                f" Current workspace: {workspace_context.get('name', 'unknown')} with "
                f"{len(workspace_context.get('documents', []))} documents, "
                f"{len(workspace_context.get('rules', []))} rules, and "
                f"{len(workspace_context.get('exclusions', []))} exclusions."
            )
        return prompt
