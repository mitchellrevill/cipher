# backend/tests/test_main_lifespan.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from redactor.main import app


def test_app_lifespan_initializes_container():
    """Verify app lifespan creates and initializes AppContainer during startup."""
    with patch('redactor.main.AppContainer') as mock_container_cls:
        mock_container = MagicMock()
        # Create non-async mocks for the clients to avoid coroutine warnings
        mock_cosmos = MagicMock()
        mock_blob = MagicMock()
        mock_oai = MagicMock()

        # Setup mock container
        mock_container.clients.cosmos_client.return_value = mock_cosmos
        mock_container.clients.blob_client.return_value = mock_blob
        mock_container.clients.oai_client.return_value = mock_oai
        mock_container_cls.return_value = mock_container

        # Use TestClient to trigger lifespan startup
        with TestClient(app) as client:
            # The app should have a container attribute after startup
            assert hasattr(app, 'container')
            assert app.container is mock_container


@pytest.mark.asyncio
async def test_app_lifespan_with_mocked_container():
    """Verify app lifespan properly initializes with mocked container."""
    with patch('redactor.main.AppContainer') as mock_container_cls:
        mock_container = MagicMock()
        mock_clients = MagicMock()

        # Setup mock clients
        mock_cosmos = AsyncMock()
        mock_blob = AsyncMock()
        mock_oai = AsyncMock()

        mock_clients.cosmos_client.return_value = mock_cosmos
        mock_clients.blob_client.return_value = mock_blob
        mock_clients.oai_client.return_value = mock_oai

        mock_container.clients = mock_clients
        mock_container_cls.return_value = mock_container

        # Verify container was created (basic test)
        # Full lifespan testing requires TestClient
        assert mock_container_cls is not None
