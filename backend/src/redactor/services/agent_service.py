from typing import Optional
from openai import AsyncAzureOpenAI
from redactor.services.job_service import JobService

class AgentService:
    """
    AI agent service for conversational redaction assistance.

    Handles chat sessions and agent turn execution with Azure OpenAI.
    """

    def __init__(self, oai_client: AsyncAzureOpenAI, job_service: JobService):
        """Initialize AgentService with OpenAI client and JobService."""
        self.oai_client = oai_client
        self.job_service = job_service
