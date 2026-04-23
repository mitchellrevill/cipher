from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceRule(BaseModel):
    """Reusable redaction rule scoped to a workspace."""

    id: str
    workspace_id: str
    pattern: str
    category: str
    confidence_threshold: float = 0.8
    applies_to: list[str] | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "rule_ssn",
                "workspace_id": "ws_123",
                "pattern": r"\d{3}-\d{2}-\d{4}",
                "category": "PII",
                "confidence_threshold": 0.95,
            }
        }
    )


class WorkspaceExclusion(BaseModel):
    """Document excluded from workspace-wide rule application."""

    id: str
    workspace_id: str
    document_id: str
    reason: str
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "excl_doc2",
                "workspace_id": "ws_123",
                "document_id": "doc_2",
                "reason": "Legal hold - do not modify",
            }
        }
    )


class Workspace(BaseModel):
    """Workspace for managing multi-document redaction campaigns."""

    id: str
    user_id: str
    name: str
    description: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    exclusion_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "ws_123",
                "user_id": "user_456",
                "name": "Q1-2026-Compliance",
                "document_ids": ["doc_1", "doc_2", "doc_3"],
                "rule_ids": ["rule_ssn", "rule_credit_card"],
                "exclusion_ids": ["excl_doc_2"],
            }
        }
    )
