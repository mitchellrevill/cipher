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
    """Create a RedactionService instance without blob storage."""
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
async def test_toggle_approval_requires_blob_client(redaction_service):
    """Approval updates require blob-backed suggestion persistence."""
    with pytest.raises(Exception, match="Blob client not available"):
        await redaction_service.toggle_approval(job_id="job-1", suggestion_id="sugg-1", approved=True)


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
async def test_add_suggestions_appends_unique_items(redaction_service_with_blob, mock_blob_client):
    existing = Suggestion(
        id="sugg-existing",
        job_id="job-1",
        text="GP",
        category="Custom",
        reasoning="Existing",
        context="",
        page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=20, y1=20)],
        approved=True,
        source="agent",
        created_at=datetime.utcnow(),
    )
    duplicate = Suggestion(
        id="sugg-duplicate",
        job_id="job-1",
        text="GP",
        category="Custom",
        reasoning="Duplicate",
        context="",
        page_num=0,
        rects=[RedactionRect(x0=10, y0=10, x1=20, y1=20)],
        approved=True,
        source="agent",
        created_at=datetime.utcnow(),
    )
    new_item = Suggestion(
        id="sugg-new",
        job_id="job-1",
        text="GP",
        category="Custom",
        reasoning="New",
        context="",
        page_num=0,
        rects=[RedactionRect(x0=30, y0=10, x1=40, y1=20)],
        approved=True,
        source="agent",
        created_at=datetime.utcnow(),
    )
    mock_blob_client.load_suggestions.return_value = [existing]

    added = await redaction_service_with_blob.add_suggestions("job-1", [duplicate, new_item])

    assert added == 1
    saved = mock_blob_client.save_suggestions.await_args.args[1]
    assert len(saved) == 2


@pytest.mark.asyncio
async def test_delete_suggestion(redaction_service_with_blob, mock_blob_client):
    """Verify deleting a suggestion from blob-backed suggestion storage."""
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

    await redaction_service_with_blob.delete_suggestion(job_id="job-1", suggestion_id="sugg-1")

    mock_blob_client.save_suggestions.assert_awaited_once_with("job-1", [])


@pytest.mark.asyncio
async def test_delete_suggestion_requires_blob_client(redaction_service):
    """Deleting suggestions requires blob-backed suggestion persistence."""
    with pytest.raises(Exception, match="Blob client not available"):
        await redaction_service.delete_suggestion(job_id="job-1", suggestion_id="sugg-1")


@pytest.mark.asyncio
async def test_delete_suggestion_is_noop_when_id_missing(redaction_service_with_blob, mock_blob_client):
    """Deleting a missing suggestion should not rewrite storage."""
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

    await redaction_service_with_blob.delete_suggestion(job_id="job-1", suggestion_id="missing")

    mock_blob_client.save_suggestions.assert_not_awaited()
