from __future__ import annotations

"""Workspace service — CRUD for workspaces, rules, and exclusions."""

import logging
from datetime import datetime
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Manage multi-document workspaces, rules, and exclusions."""

    def __init__(self, workspaces_container: Any, rules_container: Any, exclusions_container: Any):
        self.workspaces_container = workspaces_container
        self.rules_container = rules_container
        self.exclusions_container = exclusions_container

    async def create_workspace(self, user_id: str, name: str, description: str | None = None) -> dict[str, Any]:
        now = datetime.utcnow().isoformat()
        workspace = {
            "id": f"ws_{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "name": name,
            "description": description,
            "document_ids": [],
            "rule_ids": [],
            "exclusion_ids": [],
            "created_at": now,
            "updated_at": now,
            "type": "workspace",
        }
        return self.workspaces_container.create_item(body=workspace)

    async def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        try:
            workspace = self.workspaces_container.read_item(item=workspace_id, partition_key=workspace_id)
        except Exception:
            results = self._query_items(
                self.workspaces_container,
                query="SELECT * FROM c WHERE c.id = @workspace_id",
                parameters=[{"name": "@workspace_id", "value": workspace_id}],
            )
            if not results:
                return None
            workspace = results[0]

        self._ensure_workspace_lists(workspace)
        return workspace

    async def list_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        return self._query_items(
            self.workspaces_container,
            query="SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.created_at DESC",
            parameters=[{"name": "@user_id", "value": user_id}],
        )

    async def add_document(self, workspace_id: str, document_id: str) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        if document_id not in workspace["document_ids"]:
            workspace["document_ids"].append(document_id)
            workspace["updated_at"] = datetime.utcnow().isoformat()
            workspace = self._replace_workspace(workspace_id, workspace)
        return workspace

    async def remove_document(self, workspace_id: str, document_id: str) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        if document_id in workspace["document_ids"]:
            workspace["document_ids"].remove(document_id)
            workspace["updated_at"] = datetime.utcnow().isoformat()
            workspace = self._replace_workspace(workspace_id, workspace)
        return workspace

    async def assign_job(self, workspace_id: str, job_id: str, job_service) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        already_assigned = job_id in workspace["document_ids"]

        if not already_assigned:
            workspace["document_ids"].append(job_id)
            workspace["updated_at"] = datetime.utcnow().isoformat()
            self._replace_workspace(workspace_id, workspace)

        try:
            await job_service.update_workspace_id(job_id, workspace_id)
        except Exception:
            if not already_assigned:
                rollback = await self._require_workspace(workspace_id)
                rollback["document_ids"] = [doc_id for doc_id in rollback.get("document_ids", []) if doc_id != job_id]
                rollback["updated_at"] = datetime.utcnow().isoformat()
                self._replace_workspace(workspace_id, rollback)
            raise

        return await self._require_workspace(workspace_id)

    async def remove_job(self, workspace_id: str, job_id: str, job_service) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        was_present = job_id in workspace["document_ids"]

        if was_present:
            workspace["document_ids"].remove(job_id)
            workspace["updated_at"] = datetime.utcnow().isoformat()
            self._replace_workspace(workspace_id, workspace)

        try:
            await job_service.update_workspace_id(job_id, None)
        except Exception:
            if was_present:
                rollback = await self._require_workspace(workspace_id)
                if job_id not in rollback.get("document_ids", []):
                    rollback.setdefault("document_ids", []).append(job_id)
                rollback["updated_at"] = datetime.utcnow().isoformat()
                self._replace_workspace(workspace_id, rollback)
            raise

        return await self._require_workspace(workspace_id)

    async def create_rule(
        self,
        workspace_id: str,
        pattern: str,
        category: str,
        confidence_threshold: float = 0.8,
        applies_to: list[str] | None = None,
    ) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        now = datetime.utcnow().isoformat()
        rule = {
            "id": f"rule_{uuid.uuid4().hex[:8]}",
            "workspace_id": workspace_id,
            "pattern": pattern,
            "category": category,
            "confidence_threshold": confidence_threshold,
            "applies_to": applies_to,
            "created_at": now,
            "updated_at": now,
            "type": "workspace_rule",
        }
        created_rule = self.rules_container.create_item(body=rule)
        if created_rule["id"] not in workspace["rule_ids"]:
            workspace["rule_ids"].append(created_rule["id"])
            workspace["updated_at"] = now
            self._replace_workspace(workspace_id, workspace)
        return created_rule

    async def get_rules(self, workspace_id: str) -> list[dict[str, Any]]:
        return self._query_items(
            self.rules_container,
            query="SELECT * FROM c WHERE c.workspace_id = @workspace_id ORDER BY c.created_at ASC",
            parameters=[{"name": "@workspace_id", "value": workspace_id}],
        )

    async def exclude_document(self, workspace_id: str, document_id: str, reason: str) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        now = datetime.utcnow().isoformat()
        exclusion = {
            "id": f"excl_{uuid.uuid4().hex[:8]}",
            "workspace_id": workspace_id,
            "document_id": document_id,
            "reason": reason,
            "created_at": now,
            "type": "workspace_exclusion",
        }
        created_exclusion = self.exclusions_container.create_item(body=exclusion)
        if created_exclusion["id"] not in workspace["exclusion_ids"]:
            workspace["exclusion_ids"].append(created_exclusion["id"])
            workspace["updated_at"] = now
            self._replace_workspace(workspace_id, workspace)
        return created_exclusion

    async def get_exclusions(self, workspace_id: str) -> list[dict[str, Any]]:
        return self._query_items(
            self.exclusions_container,
            query="SELECT * FROM c WHERE c.workspace_id = @workspace_id ORDER BY c.created_at ASC",
            parameters=[{"name": "@workspace_id", "value": workspace_id}],
        )

    async def remove_exclusion(self, workspace_id: str, exclusion_id: str) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        if exclusion_id in workspace["exclusion_ids"]:
            workspace["exclusion_ids"].remove(exclusion_id)
            workspace["updated_at"] = datetime.utcnow().isoformat()
            self._replace_workspace(workspace_id, workspace)
        self.exclusions_container.delete_item(item=exclusion_id, partition_key=workspace_id)
        return workspace

    async def get_workspace_state(self, workspace_id: str) -> dict[str, Any] | None:
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            return None

        rules = await self.get_rules(workspace_id)
        exclusions = await self.get_exclusions(workspace_id)
        excluded_documents = {item["document_id"]: item["reason"] for item in exclusions}

        return {
            **workspace,
            "documents": [
                {
                    "id": document_id,
                    "excluded": document_id in excluded_documents,
                    "reason": excluded_documents.get(document_id),
                }
                for document_id in workspace.get("document_ids", [])
            ],
            "rules": rules,
            "exclusions": exclusions,
            "stats": {
                "document_count": len(workspace.get("document_ids", [])),
                "rule_count": len(rules),
                "exclusion_count": len(exclusions),
            },
        }

    async def _require_workspace(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")
        return workspace

    def _query_items(self, container: Any, query: str, parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items = container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        if items is None:
            return []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("type") == "workspace":
                    self._ensure_workspace_lists(item)
            return items
        return list(items)

    def _replace_workspace(self, workspace_id: str, workspace: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.workspaces_container.replace_item(item=workspace_id, body=workspace)
        except TypeError:
            raise
        except Exception as first_error:
            for partition_key in self._workspace_partition_key_candidates(workspace):
                try:
                    return self.workspaces_container.replace_item(
                        item=workspace_id,
                        body=workspace,
                        partition_key=partition_key,
                    )
                except TypeError:
                    raise
                except Exception:
                    continue
            raise first_error

    def _workspace_partition_key_candidates(self, workspace: dict[str, Any]) -> list[str]:
        candidates: list[str] = []
        for key in ("user_id", "id", "type"):
            value = workspace.get(key)
            if isinstance(value, str) and value and value not in candidates:
                candidates.append(value)
        return candidates

    def _ensure_workspace_lists(self, workspace: dict[str, Any]) -> None:
        workspace.setdefault("document_ids", [])
        workspace.setdefault("rule_ids", [])
        workspace.setdefault("exclusion_ids", [])
