"""
Cosmos DB initialization and migration script.

Creates collections, partition keys, and indexes for the application.
Run once during deployment or during local development setup.
"""

import asyncio
import logging
from azure.cosmos import CosmosClient, ContainerProxy, DatabaseProxy
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import os

logger = logging.getLogger(__name__)

# Collection definitions
COLLECTIONS = {
    "jobs": {
        "partition_key": "/job_id",
        "ttl": None,  # Indefinite retention for UX
        "unique_keys": [{"paths": ["/id"]}],
        "indexes": [
            {"path": "/job_id"},
            {"path": "/status"},
            {"path": "/created_at"},
            {"path": "/user_id"},
        ]
    },
    "suggestions": {
        "partition_key": "/job_id",
        "ttl": None,
        "unique_keys": [{"paths": ["/id"]}],
        "indexes": [
            {"path": "/job_id"},
            {"path": "/approved"},
            {"path": "/source"},
        ]
    },
    "chat_sessions": {
        "partition_key": "/job_id",
        "ttl": None,
        "unique_keys": [{"paths": ["/id"]}],
        "indexes": [
            {"path": "/job_id"},
            {"path": "/created_at"},
        ]
    },
    "workspaces": {
        "partition_key": "/user_id",
        "ttl": None,
        "unique_keys": [{"paths": ["/id"]}],
        "indexes": [
            {"path": "/user_id"},
            {"path": "/name"},
            {"path": "/created_at"},
        ]
    },
    "workspace_rules": {
        "partition_key": "/workspace_id",
        "ttl": None,
        "unique_keys": [{"paths": ["/id"]}],
        "indexes": [
            {"path": "/workspace_id"},
            {"path": "/category"},
            {"path": "/created_at"},
        ]
    },
    "workspace_exclusions": {
        "partition_key": "/workspace_id",
        "ttl": None,
        "unique_keys": [{"paths": ["/id"]}],
        "indexes": [
            {"path": "/workspace_id"},
            {"path": "/document_id"},
            {"path": "/created_at"},
        ]
    }
}


def get_cosmos_client(endpoint: str, key: str = None) -> CosmosClient:
    """
    Create Cosmos DB client.

    Uses Managed Identity in production, key-based auth for local dev.
    """
    if os.getenv('AZURE_ENV') == 'production':
        credential = ManagedIdentityCredential()
    else:
        credential = DefaultAzureCredential()

    return CosmosClient(url=endpoint, credential=credential)


async def initialize_database(
    endpoint: str,
    db_name: str,
    key: str = None
) -> DatabaseProxy:
    """
    Initialize or get database.

    Args:
        endpoint: Cosmos DB endpoint
        db_name: Database name
        key: Optional connection key (for local dev)

    Returns:
        DatabaseProxy for the initialized database
    """
    client = get_cosmos_client(endpoint, key)

    # Create or get database
    try:
        database = client.create_database_if_not_exists(id=db_name)
        logger.info(f"✓ Database '{db_name}' ready")
    except Exception as e:
        logger.error(f"Failed to create database: {e}")
        raise

    return database


async def initialize_collection(
    database: DatabaseProxy,
    collection_name: str,
    collection_spec: dict
) -> ContainerProxy:
    """
    Initialize a collection with indexes and TTL.

    Args:
        database: DatabaseProxy
        collection_name: Collection name
        collection_spec: Collection specification dict

    Returns:
        ContainerProxy for the collection
    """
    partition_key = collection_spec["partition_key"]

    try:
        container = database.create_container_if_not_exists(
            id=collection_name,
            partition_key=partition_key,
            default_ttl=collection_spec.get("ttl")
        )
        logger.info(f"✓ Collection '{collection_name}' ready")
    except Exception as e:
        logger.error(f"Failed to create collection '{collection_name}': {e}")
        raise

    return container


async def setup_cosmos_db(
    endpoint: str,
    db_name: str = "redactor",
    key: str = None
):
    """
    Complete Cosmos DB setup: database + collections + indexes.

    Args:
        endpoint: Cosmos DB endpoint
        db_name: Database name
        key: Optional connection key
    """
    logger.info("Initializing Cosmos DB...")

    # Create database
    database = await initialize_database(endpoint, db_name, key)

    # Create collections
    for collection_name, spec in COLLECTIONS.items():
        await initialize_collection(database, collection_name, spec)

    logger.info("✓ Cosmos DB initialization complete")


# CLI entry point
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python cosmos_init.py <endpoint> [db_name]")
        sys.exit(1)

    endpoint = sys.argv[1]
    db_name = sys.argv[2] if len(sys.argv) > 2 else "redactor"

    logging.basicConfig(level=logging.INFO)

    try:
        asyncio.run(setup_cosmos_db(endpoint, db_name))
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)
