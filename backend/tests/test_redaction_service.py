"""Tests for RedactionService."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from redactor.services.redaction_service import RedactionService
from redactor.models import Suggestion, RedactionRect


@pytest.fixture
def mock_cosmos_client():
    """Create a mock Cosmos DB client."""
    return MagicMock()


@pytest.fixture
def redaction_service(mock_cosmos_client):
    """Create a RedactionService instance with mocked Cosmos client."""
    return RedactionService(cosmos_client=mock_cosmos_client)


@pytest.fixture
def mock_blob_client():
    """Create a mock blob client for approval persistence tests."""
    client = MagicMock()
    client.load_suggestions = AsyncMock(return_value=[])
    client.save_suggestions = AsyncMock(return_value=None)
    return client


@pytest.fixture
def redaction_service_with_blob(mock_cosmos_client, mock_blob_client):
    """Create a RedactionService instance configured with blob storage."""
    return RedactionService(cosmos_client=mock_cosmos_client, blob_client=mock_blob_client)


@pytest.mark.asyncio
async def test_save_suggestions(redaction_service, mock_cosmos_client):
    """Verify saving suggestions to Cosmos DB."""
    now = datetime.utcnow()
    suggestions = [
        {
            "id": "sugg-1",
            "text": "John Smith",
            "category": "Person",
            "reasoning": "PII",
            "context": "found in paragraph 2",
            "page_num": 0,
            "rects": [],
            "approved": False,
            "source": "ai",
            "created_at": now.isoformat()
        }
    ]

    mock_cosmos_client.create_item.return_value = {
        "id": "sugg-1",
        "job_id": "job-1",
        "text": "John Smith",
        "category": "Person",
        "reasoning": "PII",
        "context": "found in paragraph 2",
        "page_num": 0,
        "rects": [],
        "approved": False,
        "source": "ai",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }

    result = await redaction_service.save_suggestions(job_id="job-1", suggestions=suggestions)

    assert result is not None
    assert len(result) > 0
    mock_cosmos_client.create_item.assert_called_once()


@pytest.mark.asyncio
async def test_get_suggestions(redaction_service, mock_cosmos_client):
    """Verify getting suggestions for a job."""
    now = datetime.utcnow()
    mock_cosmos_client.query_items.return_value = [
        {
            "id": "sugg-1",
            "job_id": "job-1",
            "text": "John Smith",
            "category": "Person",
            "reasoning": "PII",
            "context": "found in paragraph 2",
            "page_num": 0,
            "rects": [],
            "approved": False,
            "source": "ai",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
    ]

    suggestions = await redaction_service.get_suggestions(job_id="job-1")

    assert len(suggestions) > 0
    assert suggestions[0].job_id == "job-1"
    assert suggestions[0].text == "John Smith"


@pytest.mark.asyncio
async def test_toggle_approval(redaction_service_with_blob, mock_blob_client):
    """Verify toggling suggestion approval via blob persistence."""
    suggestion = Suggestion(
        id="sugg-1",
        job_id="job-1",
        text="John Smith",
        category="Person",
        reasoning="PII",
        context="found in paragraph 2",
        page_num=0,
        rects=[],
        approved=False,
        source="ai",
        created_at=datetime.utcnow(),
    )
    mock_blob_client.load_suggestions.return_value = [suggestion]

    await redaction_service_with_blob.toggle_approval(job_id="job-1", suggestion_id="sugg-1", approved=True)

    assert suggestion.approved is True
    mock_blob_client.save_suggestions.assert_awaited_once_with("job-1", [suggestion])


@pytest.mark.asyncio
async def test_bulk_update_approvals_updates_only_matching_suggestions(redaction_service_with_blob, mock_blob_client):
    """Verify bulk approval updates happen in one load/save cycle."""
    suggestions = [
        Suggestion(
            id="sugg-1",
            job_id="job-1",
            text="John Smith",
            category="Person",
            reasoning="PII",
            context="found in paragraph 2",
            page_num=0,
            rects=[],
            approved=False,
            source="ai",
            created_at=datetime.utcnow(),
        ),
        Suggestion(
            id="sugg-2",
            job_id="job-1",
            text="Already Approved",
            category="Person",
            reasoning="PII",
            context="found in paragraph 3",
            page_num=1,
            rects=[],
            approved=True,
            source="ai",
            created_at=datetime.utcnow(),
        ),
    ]
    mock_blob_client.load_suggestions.return_value = suggestions

    updated_count = await redaction_service_with_blob.bulk_update_approvals("job-1", True)

    assert updated_count == 1
    assert suggestions[0].approved is True
    assert suggestions[1].approved is True
    mock_blob_client.save_suggestions.assert_awaited_once_with("job-1", suggestions)


@pytest.mark.asyncio
async def test_add_manual_suggestion(redaction_service_with_blob, mock_blob_client):
    """Verify adding a manually created suggestion."""
    now = datetime.utcnow()
    rect = RedactionRect(x0=0, y0=0, x1=100, y1=20)
    suggestion = Suggestion(
        id="sugg-manual-1",
        job_id="job-1",
        text="jane@example.com",
        category="Email",
        reasoning="Email address",
        context="Contact info section",
        page_num=1,
        rects=[rect],
        approved=False,
        source="manual",
        created_at=now,
        updated_at=now
    )

    mock_blob_client.load_suggestions.return_value = []

    await redaction_service_with_blob.add_manual_suggestion(job_id="job-1", suggestion=suggestion)

    mock_blob_client.save_suggestions.assert_awaited_once_with("job-1", [suggestion])


@pytest.mark.asyncio
async def test_delete_suggestion(redaction_service, mock_cosmos_client):
    """Verify deleting a suggestion."""
    await redaction_service.delete_suggestion(job_id="job-1", suggestion_id="sugg-1")

    mock_cosmos_client.delete_item.assert_called_once()


@pytest.mark.asyncio
async def test_get_suggestions_empty(redaction_service, mock_cosmos_client):
    """Verify getting suggestions when none exist."""
    mock_cosmos_client.query_items.return_value = []

    suggestions = await redaction_service.get_suggestions(job_id="job-nonexistent")

    assert len(suggestions) == 0


@pytest.mark.asyncio
async def test_get_suggestions_exception_handling(redaction_service, mock_cosmos_client):
    """Verify exception handling when querying suggestions."""
    mock_cosmos_client.query_items.side_effect = Exception("Query error")

    suggestions = await redaction_service.get_suggestions(job_id="job-1")

    assert len(suggestions) == 0
