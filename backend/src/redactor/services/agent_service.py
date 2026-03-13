"""AI agent service for conversational redaction assistance."""

from typing import Optional, Dict
from datetime import datetime
import uuid
import logging

from redactor.agent.agent_loop import AgentLoop
from redactor.agent.tools.registry import ToolRegistry
from redactor.agent.tools.search import SearchTool
from redactor.agent.tools.workspace import (
    GetWorkspaceStateTool,
    CreateRuleTool,
    ApplyRuleTool,
    ExcludeDocumentTool
)
from redactor.agent.knowledge_base import KnowledgeBase
from redactor.config import get_settings
from redactor.services.job_service import JobService
from redactor.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)


class AgentService:
    """
    AI agent service for conversational assistance with document redaction.

    Manages chat sessions and uses an agent loop with tool execution for
    context-aware responses about redaction decisions.
    """

    def __init__(
        self,
        oai_client,
        job_service: JobService,
        workspace_service: Optional[WorkspaceService] = None,
    ):
        """
        Initialize AgentService with agent framework components.

        Args:
            oai_client: Azure OpenAI async client
            job_service: JobService for accessing job context
            workspace_service: WorkspaceService for managing workspaces
        """
        self.oai_client = oai_client
        self.job_service = job_service
        self.workspace_service = workspace_service
        self.settings = get_settings()
        self.sessions = {}  # In-memory session cache; will use Cosmos DB (Task 9)

        # Initialize knowledge base
        self.knowledge_base = KnowledgeBase(workspace_service=workspace_service)

        # Initialize tool registry
        self.tool_registry = ToolRegistry()
        self._register_tools()

        # Initialize agent loop
        self.agent_loop = AgentLoop(
            tool_registry=self.tool_registry,
            oai_client=oai_client,
            knowledge_base=self.knowledge_base
        )

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

    def _register_tools(self):
        """Register all available tools with the registry."""
        self.tool_registry.register(SearchTool(job_service=self.job_service))
        self.tool_registry.register(GetWorkspaceStateTool(workspace_service=self.workspace_service))
        self.tool_registry.register(CreateRuleTool(workspace_service=self.workspace_service))
        self.tool_registry.register(ApplyRuleTool(workspace_service=self.workspace_service))
        self.tool_registry.register(ExcludeDocumentTool(workspace_service=self.workspace_service))

    async def run_turn(
        self,
        job_id: str,
        message: str,
        previous_response_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict:
        """
        Run an agent turn using the agent loop.

        Sends message to agent loop with job context, receives response with
        tool executions and directives.

        Args:
            job_id: Job identifier for context
            message: User message
            previous_response_id: Optional ID of previous response for continuation
            workspace_id: Optional workspace ID for context
            session_id: Optional session ID for conversation history

        Returns:
            Dict with text, response_id, tool_calls, and directives
        """
        try:
            # Verify job exists
            job = await self.job_service.get_job(job_id)
            if not job:
                return {
                    "text": f"Job '{job_id}' not found",
                    "response_id": None,
                    "tool_calls": [],
                    "directives": [],
                }

            # Update workspace in session if provided
            if session_id and workspace_id and session_id in self.sessions:
                self.sessions[session_id]["workspace_id"] = workspace_id

            # Get session messages for context
            session_messages = []
            if session_id and session_id in self.sessions:
                session_messages = [
                    {"role": msg["role"], "content": msg["text"]}
                    for msg in self.sessions[session_id].get("messages", [])[-6:]
                ]

            # Run agent turn via agent loop
            response = await self.agent_loop.run_turn(
                user_message=message,
                job_id=job_id,
                workspace_id=workspace_id,
                session_messages=session_messages
            )

            response["response_id"] = response.get("response_id") or str(uuid.uuid4())
            return response

        except Exception:
            logger.exception("Error in agent turn")
            return {
                "text": "Error processing request",
                "response_id": None,
                "tool_calls": [],
                "directives": [],
            }
