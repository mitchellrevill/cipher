"""Test Cosmos DB initialization script."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.db.cosmos_init import (
    initialize_database,
    initialize_collection,
    setup_cosmos_db,
    COLLECTIONS
)


@pytest.mark.asyncio
async def test_initialize_database():
    """Verify database initialization."""
    with patch('redactor.db.cosmos_init.get_cosmos_client') as mock_client_fn:
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_client.create_database_if_not_exists.return_value = mock_database
        mock_client_fn.return_value = mock_client

        db = await initialize_database("https://test.documents.azure.com:443/", "testdb")

        assert db is not None
        mock_client.create_database_if_not_exists.assert_called_once_with(id="testdb")


@pytest.mark.asyncio
async def test_initialize_collection():
    """Verify collection initialization."""
    mock_database = MagicMock()
    mock_container = MagicMock()
    mock_database.create_container_if_not_exists.return_value = mock_container

    spec = COLLECTIONS["jobs"]
    container = await initialize_collection(mock_database, "jobs", spec)

    assert container is not None
    mock_database.create_container_if_not_exists.assert_called_once_with(
        id="jobs",
        partition_key="/job_id",
        default_ttl=None
    )


@pytest.mark.asyncio
async def test_collections_have_required_fields():
    """Verify all collections have required configuration."""
    required_fields = {"partition_key", "ttl", "unique_keys", "indexes"}

    for collection_name, spec in COLLECTIONS.items():
        assert required_fields.issubset(spec.keys()), \
            f"Collection '{collection_name}' missing required fields"
        assert spec["partition_key"].startswith("/"), \
            f"Collection '{collection_name}' partition key must start with '/'"


@pytest.mark.asyncio
async def test_setup_cosmos_db():
    """Verify complete Cosmos DB setup."""
    with patch('redactor.db.cosmos_init.initialize_database') as mock_init_db:
        with patch('redactor.db.cosmos_init.initialize_collection') as mock_init_coll:
            mock_database = MagicMock()
            mock_init_db.return_value = mock_database
            mock_init_coll.return_value = MagicMock()

            await setup_cosmos_db("https://test.documents.azure.com:443/", "testdb")

            # Verify database initialized
            mock_init_db.assert_called_once()

            # Verify all configured collections initialized
            assert mock_init_coll.call_count == len(COLLECTIONS)
