from datetime import datetime

from redactor.models import Workspace, WorkspaceExclusion, WorkspaceRule


def test_workspace_creation():
    workspace = Workspace(
        id="ws_test",
        user_id="user_123",
        name="Q1-Compliance",
        document_ids=["doc1", "doc2"],
        created_at=datetime.utcnow(),
    )

    assert workspace.id == "ws_test"
    assert workspace.name == "Q1-Compliance"
    assert len(workspace.document_ids) == 2


def test_workspace_rule_creation():
    rule = WorkspaceRule(
        id="rule_ssn",
        workspace_id="ws_test",
        pattern=r"\d{3}-\d{2}-\d{4}",
        category="PII",
        confidence_threshold=0.9,
        created_at=datetime.utcnow(),
    )

    assert rule.pattern == r"\d{3}-\d{2}-\d{4}"
    assert rule.category == "PII"


def test_workspace_exclusion_creation():
    exclusion = WorkspaceExclusion(
        id="excl_doc2",
        workspace_id="ws_test",
        document_id="doc2",
        reason="Legal hold",
        created_at=datetime.utcnow(),
    )

    assert exclusion.document_id == "doc2"
    assert exclusion.reason == "Legal hold"
