from typing import Optional
from azure.cosmos import CosmosClient

class JobService:
    """
    Job lifecycle management service.

    Handles creation, retrieval, and state management of document processing jobs.
    Persists job data to Cosmos DB.
    """

    def __init__(self, cosmos_client: CosmosClient):
        """Initialize JobService with Cosmos DB client."""
        self.cosmos_client = cosmos_client
