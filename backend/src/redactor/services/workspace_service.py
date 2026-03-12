from __future__ import annotations

"""Workspace CRUD and state management service."""

from datetime import datetime
import inspect
from typing import Any
import uuid

from redactor.config import get_settings


class WorkspaceService:
    """Manage multi-document workspaces, rules, and exclusions."""

    def __init__(self, cosmos_client: Any):
        self.cosmos_client = cosmos_client
        self.settings = get_settings()
        self._database = None
        self._workspaces_container = None
        self._rules_container = None
        self._exclusions_container = None

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
        container = self._get_workspaces_container()
        return await self._call(container.create_item, body=workspace)

    async def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        container = self._get_workspaces_container()

        if container is self.cosmos_client and hasattr(container, "read_item"):
            try:
                return await self._call(container.read_item, item=workspace_id, partition_key=workspace_id)
            except Exception:
                pass

        results = await self._query_items(
            container,
            query="SELECT * FROM c WHERE c.id = @workspace_id",
            parameters=[{"name": "@workspace_id", "value": workspace_id}],
        )
        return results[0] if results else None

    async def list_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        container = self._get_workspaces_container()
        return await self._query_items(
            container,
            query="SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.created_at DESC",
            parameters=[{"name": "@user_id", "value": user_id}],
        )

    async def add_document(self, workspace_id: str, document_id: str) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        if document_id not in workspace["document_ids"]:
            workspace["document_ids"].append(document_id)
            workspace["updated_at"] = datetime.utcnow().isoformat()
            workspace = await self._call(self._get_workspaces_container().upsert_item, body=workspace)
        return workspace

    async def remove_document(self, workspace_id: str, document_id: str) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        if document_id in workspace["document_ids"]:
            workspace["document_ids"].remove(document_id)
            workspace["updated_at"] = datetime.utcnow().isoformat()
            workspace = await self._call(self._get_workspaces_container().upsert_item, body=workspace)
        return workspace

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
        created_rule = await self._call(self._get_rules_container().create_item, body=rule)
        if created_rule["id"] not in workspace["rule_ids"]:
            workspace["rule_ids"].append(created_rule["id"])
            workspace["updated_at"] = now
            await self._call(self._get_workspaces_container().upsert_item, body=workspace)
        return created_rule

    async def get_rules(self, workspace_id: str) -> list[dict[str, Any]]:
        return await self._query_items(
            self._get_rules_container(),
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
        created_exclusion = await self._call(self._get_exclusions_container().create_item, body=exclusion)
        if created_exclusion["id"] not in workspace["exclusion_ids"]:
            workspace["exclusion_ids"].append(created_exclusion["id"])
            workspace["updated_at"] = now
            await self._call(self._get_workspaces_container().upsert_item, body=workspace)
        return created_exclusion

    async def get_exclusions(self, workspace_id: str) -> list[dict[str, Any]]:
        return await self._query_items(
            self._get_exclusions_container(),
            query="SELECT * FROM c WHERE c.workspace_id = @workspace_id ORDER BY c.created_at ASC",
            parameters=[{"name": "@workspace_id", "value": workspace_id}],
        )

    async def remove_exclusion(self, workspace_id: str, exclusion_id: str) -> dict[str, Any]:
        workspace = await self._require_workspace(workspace_id)
        if exclusion_id in workspace["exclusion_ids"]:
            workspace["exclusion_ids"].remove(exclusion_id)
            workspace["updated_at"] = datetime.utcnow().isoformat()
            await self._call(self._get_workspaces_container().upsert_item, body=workspace)
        await self._call(self._get_exclusions_container().delete_item, item=exclusion_id, partition_key=workspace_id)
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
        workspace.setdefault("document_ids", [])
        workspace.setdefault("rule_ids", [])
        workspace.setdefault("exclusion_ids", [])
        return workspace

    async def _query_items(self, container: Any, query: str, parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items = await self._call(
            container.query_items,
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        if items is None:
            return []
        if isinstance(items, list):
            return items
        return list(items)

    async def _call(self, func, *args, **kwargs):
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _get_database(self):
        if self._database is None:
            get_database_client = getattr(self.cosmos_client, "get_database_client", None)
            if get_database_client is None or inspect.iscoroutinefunction(get_database_client):
                return None

            database = get_database_client(self.settings.cosmos_db_name)
            if inspect.isawaitable(database):
                return None

            self._database = database
        return self._database

    def _get_workspaces_container(self):
        if self._workspaces_container is None:
            self._workspaces_container = self._get_container("workspaces")
        return self._workspaces_container

    def _get_rules_container(self):
        if self._rules_container is None:
            self._rules_container = self._get_container("workspace_rules")
        return self._rules_container

    def _get_exclusions_container(self):
        if self._exclusions_container is None:
            self._exclusions_container = self._get_container("workspace_exclusions")
        return self._exclusions_container

    def _get_container(self, container_name: str):
        database = self._get_database()
        if database is not None:
            return database.get_container_client(container_name)
        return self.cosmos_client
