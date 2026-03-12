from __future__ import annotations

"""Workspace-aware redaction orchestrator with tool execution and directives."""

from typing import Any
import logging
import re
import uuid

from openai import AsyncAzureOpenAI

from redactor.agent.workspace_tools import WorkspaceToolbox
from redactor.config import get_settings
from redactor.services.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


class RedactionOrchestrator:
    """Main orchestrator agent for conversational PDF redaction assistance."""

    def __init__(
        self,
        oai_client: AsyncAzureOpenAI,
        job_service,
        redaction_service,
        workspace_service=None,
        rule_engine: RuleEngine | None = None,
    ):
        self.oai_client = oai_client
        self.settings = get_settings()
        self.rule_engine = rule_engine or RuleEngine()
        self.toolbox = WorkspaceToolbox(
            job_service=job_service,
            redaction_service=redaction_service,
            workspace_service=workspace_service,
            rule_engine=self.rule_engine,
        )
        self.tools = self._define_tools()
        self.system_prompt = self._create_system_prompt()
        self.max_tool_rounds = 10

    def _define_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "search_document",
                "description": "Search for text in the current document or workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for"},
                        "doc_id": {"type": "string", "description": "Optional document identifier"},
                    },
                    "required": ["query"],
                },
            },
            {
                "type": "function",
                "name": "get_workspace_state",
                "description": "Return the current workspace documents, rules, and exclusions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string", "description": "Workspace identifier"}
                    },
                    "required": ["workspace_id"],
                },
            },
            {
                "type": "function",
                "name": "get_redaction_summary",
                "description": "Summarize approved and pending redactions for a document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "string", "description": "Document identifier"}
                    },
                    "required": ["doc_id"],
                },
            },
            {
                "type": "function",
                "name": "apply_batch_rule",
                "description": "Apply a saved workspace rule across non-excluded documents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string", "description": "Workspace identifier"},
                        "rule_id": {"type": "string", "description": "Workspace rule identifier"},
                    },
                    "required": ["workspace_id", "rule_id"],
                },
            },
        ]

    def _create_system_prompt(self) -> str:
        return (
            "You are an intelligent PDF redaction assistant powered by a workspace-aware orchestration layer. "
            "Help users search documents, reason about redaction rules, and explain what actions you take. "
            "Always respect workspace exclusions and be explicit about scope when multiple documents are involved."
        )

    async def run_turn(
        self,
        user_message: str,
        job_id: str,
        workspace_context: dict[str, Any] | None = None,
        session_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        lowered = user_message.lower()
        tool_calls: list[dict[str, Any]] = []
        directives: list[dict[str, Any]] = []
        active_workspace_id = workspace_context.get("id") if workspace_context else None
        target_doc_id = self._resolve_target_doc_id(job_id, user_message, workspace_context)

        page_request = self._extract_page_number(user_message)
        if page_request is not None and any(keyword in lowered for keyword in ("jump", "go to", "open", "page ", "navigate")):
            directives.append({"type": "jump_to_page", "page": page_request, "document_id": target_doc_id})
            return self._response(
                text=f"Jumping to [[page:{page_request}]].",
                tool_calls=tool_calls,
                directives=directives,
            )

        if "list workspaces" in lowered or "available workspaces" in lowered:
            workspaces = await self.toolbox.list_workspaces()
            tool_calls.append(self._tool_call("list_workspaces", {}, {"count": len(workspaces)}))
            if not workspaces:
                return self._response("No workspaces exist yet. Create one and I can help organize documents and rules.", tool_calls, directives)
            lines = [f"- {workspace['name']} (`{workspace['id']}`): {workspace['doc_count']} docs, {workspace['rule_count']} rules" for workspace in workspaces]
            return self._response("Available workspaces:\n" + "\n".join(lines), tool_calls, directives)

        if active_workspace_id and self._is_workspace_state_request(lowered):
            state = await self.toolbox.get_workspace_state(active_workspace_id)
            tool_calls.append(self._tool_call("get_workspace_state", {"workspace_id": active_workspace_id}, {"found": state is not None}))
            if not state:
                return self._response("I couldn't load the current workspace state.", tool_calls, directives)
            text = self._format_workspace_state(state)
            return self._response(text, tool_calls, directives)

        if active_workspace_id and ("exclude" in lowered or "don't redact" in lowered or "do not redact" in lowered):
            reason = self._extract_reason(user_message)
            result = await self.toolbox.exclude_document(active_workspace_id, target_doc_id, reason)
            tool_calls.append(self._tool_call("exclude_document", {"workspace_id": active_workspace_id, "doc_id": target_doc_id}, result))
            directives.append({"type": "refresh_workspace", "workspace_id": active_workspace_id})
            return self._response(
                f"Excluded `{target_doc_id}` from workspace automation. Reason: {result.get('reason', reason)}.",
                tool_calls,
                directives,
            )

        if active_workspace_id and ("remove exclusion" in lowered or "include again" in lowered or "unexclude" in lowered):
            exclusion = self._find_exclusion_for_doc(workspace_context, target_doc_id)
            if not exclusion:
                return self._response("That document is not currently excluded.", tool_calls, directives)
            result = await self.toolbox.remove_exclusion(active_workspace_id, exclusion["id"])
            tool_calls.append(self._tool_call("remove_exclusion", {"workspace_id": active_workspace_id, "exclusion_id": exclusion["id"]}, result))
            directives.append({"type": "refresh_workspace", "workspace_id": active_workspace_id})
            return self._response(f"Removed the exclusion for `{target_doc_id}`. It can participate in workspace rules again.", tool_calls, directives)

        if active_workspace_id and ("create rule" in lowered or "save rule" in lowered):
            rule_def = self.rule_engine.infer_rule_definition(user_message)
            if not rule_def:
                return self._response("I couldn't infer a reusable rule pattern yet. Try naming the pattern or quoting the exact text.", tool_calls, directives)
            result = await self.toolbox.create_workspace_rule(active_workspace_id, rule_def)
            tool_calls.append(self._tool_call("create_workspace_rule", {"workspace_id": active_workspace_id, "rule_def": rule_def}, result))
            directives.append({"type": "refresh_workspace", "workspace_id": active_workspace_id})
            return self._response(
                f"Saved a workspace rule `{result.get('rule_id')}` for category **{rule_def['category']}** using pattern `{rule_def['pattern']}`.",
                tool_calls,
                directives,
            )

        if active_workspace_id and "apply rule" in lowered:
            rules = workspace_context.get("rules", []) if workspace_context else []
            rule = self.rule_engine.resolve_rule(user_message, rules)
            if not rule:
                return self._response("There isn't a saved workspace rule to apply yet.", tool_calls, directives)
            result = await self.toolbox.apply_batch_rule(active_workspace_id, rule["id"])
            tool_calls.append(self._tool_call("apply_batch_rule", {"workspace_id": active_workspace_id, "rule_id": rule["id"]}, result))
            directives.append({"type": "refresh_workspace", "workspace_id": active_workspace_id})
            return self._response(self._format_batch_rule_result(rule, result), tool_calls, directives)

        if any(keyword in lowered for keyword in ("search", "find", "look for", "locate")):
            query = self._extract_search_query(user_message)
            results = await self.toolbox.search_document(query=query, doc_id=target_doc_id, workspace_id=active_workspace_id if target_doc_id != job_id else None)
            tool_calls.append(self._tool_call("search_document", {"query": query, "doc_id": target_doc_id}, {"count": len(results)}))
            if not results:
                return self._response(f"I couldn't find `{query}` in the current search scope.", tool_calls, directives)
            first_result = results[0]
            directives.append({
                "type": "highlight_text",
                "document_id": first_result["document_id"],
                "page": first_result["page"],
                "suggestion_id": first_result.get("suggestion_id"),
                "rects": first_result.get("coords", []),
            })
            directives.append({"type": "jump_to_page", "document_id": first_result["document_id"], "page": first_result["page"]})
            return self._response(self._format_search_results(query, results), tool_calls, directives)

        if any(keyword in lowered for keyword in ("suggest", "what should", "what else should", "missed")):
            result = await self.toolbox.suggest_redactions(target_doc_id)
            tool_calls.append(self._tool_call("suggest_redactions", {"doc_id": target_doc_id}, {"found": result is not None}))
            if not result:
                return self._response("I couldn't load suggestion data for that document.", tool_calls, directives)
            first = result["suggestions"][0] if result["suggestions"] else None
            if first:
                directives.append({"type": "jump_to_page", "document_id": target_doc_id, "page": first["page"]})
                directives.append({"type": "focus_suggestion", "suggestion_id": first["id"], "document_id": target_doc_id})
            return self._response(self._format_suggestions(result), tool_calls, directives)

        if any(keyword in lowered for keyword in ("summary", "status", "how many", "approved", "pending", "riskiest")):
            summary = await self.toolbox.get_redaction_summary(target_doc_id)
            tool_calls.append(self._tool_call("get_redaction_summary", {"doc_id": target_doc_id}, {"found": summary is not None}))
            if not summary:
                return self._response("I couldn't load the redaction summary for that document.", tool_calls, directives)
            return self._response(self._format_redaction_summary(summary), tool_calls, directives)

        if any(keyword in lowered for keyword in ("approve", "redact this text", "mark this")):
            quoted = self.rule_engine._extract_quoted_text(user_message)
            if quoted:
                result = await self.toolbox.add_redaction(target_doc_id, quoted)
                tool_calls.append(self._tool_call("add_redaction", {"doc_id": target_doc_id, "text": quoted}, result))
                return self._response(result.get("message", "Updated matching suggestions."), tool_calls, directives)

        fallback = await self._generate_fallback_response(user_message, job_id=job_id, workspace_context=workspace_context, session_messages=session_messages)
        return self._response(fallback, tool_calls, directives)

    def _build_context_string(self, workspace_context: dict[str, Any] | None) -> str:
        if not workspace_context:
            return ""

        lines: list[str] = []
        lines.append(f"Workspace: {workspace_context.get('name', 'N/A')}")

        documents = workspace_context.get("documents", [])
        exclusions = workspace_context.get("exclusions", [])
        lines.append(f"Documents in workspace: {len(documents)}")
        lines.append(f"Excluded documents: {len(exclusions)}")

        rules = workspace_context.get("rules", [])
        if rules:
            lines.append(f"Active rules: {len(rules)}")

        return "\n".join(lines)

    def _format_workspace_state(self, state: dict[str, Any]) -> str:
        documents = state.get("documents", [])
        rules = state.get("rules", [])
        exclusions = state.get("exclusions", [])
        lines = [f"Workspace **{state.get('name', 'Unknown')}** currently has {len(documents)} documents."]
        if documents:
            lines.append("Documents:")
            for document in documents[:8]:
                label = document.get("filename") or document.get("id")
                suffix = " (excluded)" if document.get("excluded") else ""
                lines.append(f"- {label}{suffix}")
        if rules:
            lines.append("Rules:")
            for rule in rules[:6]:
                lines.append(f"- `{rule.get('id')}` · {rule.get('category')} · `{rule.get('pattern')}`")
        if exclusions:
            lines.append("Exclusions:")
            for exclusion in exclusions[:6]:
                lines.append(f"- `{exclusion.get('document_id')}` — {exclusion.get('reason')}")
        return "\n".join(lines)

    def _format_batch_rule_result(self, rule: dict[str, Any], result: dict[str, Any]) -> str:
        if result.get("status") == "error":
            return result.get("message", "The batch rule could not be applied.")

        lines = [
            f"Applied rule `{rule.get('id')}` across the workspace.",
            f"Approved {result.get('applied_count', 0)} suggestion{'s' if result.get('applied_count', 0) != 1 else ''}.",
        ]
        affected_docs = result.get("affected_docs", [])
        if affected_docs:
            lines.append("Affected documents:")
            for document in affected_docs:
                pages = ", ".join(str(page) for page in document.get("pages", [])) or "n/a"
                lines.append(
                    f"- `{document.get('document_id')}`: {document.get('approved_count')} approved across page(s) {pages}"
                )
        skipped = result.get("skipped", [])
        if skipped:
            lines.append("Skipped excluded documents: " + ", ".join(f"`{doc}`" for doc in skipped))
        return "\n".join(lines)

    def _format_search_results(self, query: str, results: list[dict[str, Any]]) -> str:
        lines = [f"Found {len(results)} match{'es' if len(results) != 1 else ''} for `{query}`."]
        for result in results[:5]:
            filename = result.get("filename") or result.get("document_id")
            lines.append(
                f"- **{filename}** [[page:{result['page']}]] · {result.get('text') or 'match'}"
            )
        return "\n".join(lines)

    def _format_suggestions(self, result: dict[str, Any]) -> str:
        pending_count = result.get("pending_count", 0)
        approved_count = result.get("approved_count", 0)
        lines = [f"This document has {pending_count} pending and {approved_count} approved suggestions."]
        suggestions = result.get("suggestions", [])
        if suggestions:
            lines.append("Top pending suggestions:")
            for suggestion in suggestions[:5]:
                lines.append(
                    f"- **{suggestion.get('category')}** [[page:{suggestion.get('page')}]] · {suggestion.get('text') or 'Untitled suggestion'}"
                )
        return "\n".join(lines)

    def _format_redaction_summary(self, summary: dict[str, Any]) -> str:
        category_bits = ", ".join(f"{category}: {count}" for category, count in summary.get("by_category", {}).items())
        lines = [
            f"**{summary.get('filename') or summary.get('doc_id')}** is `{summary.get('status')}`.",
            f"Approved: {summary.get('approved', 0)} · Pending: {summary.get('pending', 0)}",
        ]
        if category_bits:
            lines.append("By category: " + category_bits)
        return "\n".join(lines)

    async def _generate_fallback_response(
        self,
        user_message: str,
        job_id: str,
        workspace_context: dict[str, Any] | None,
        session_messages: list[dict[str, Any]] | None,
    ) -> str:
        context_str = self._build_context_string(workspace_context)
        if self.settings.azure_openai_endpoint and self.settings.azure_openai_key and getattr(self.oai_client, "chat", None):
            try:
                history = session_messages[-6:] if session_messages else []
                response = await self.oai_client.chat.completions.create(
                    model=self.settings.azure_openai_deployment,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "system", "content": f"Active document id: {job_id}\n{context_str}"},
                        *[
                            {"role": message["role"], "content": message["text"]}
                            for message in history
                            if message.get("role") in {"user", "assistant"} and message.get("text")
                        ],
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.2,
                    max_tokens=400,
                )
                return response.choices[0].message.content or "I'm ready to help with this redaction workflow."
            except Exception:
                logger.exception("Falling back to canned orchestrator response")

        response_text = "I’m ready to help with workspace-aware redaction tasks."
        if context_str:
            response_text += f" Current scope:\n{context_str}"
        if session_messages:
            response_text += f"\nConversation turns loaded: {len(session_messages)}"
        response_text += "\nTry asking me to search, summarize, create a rule, or apply a saved rule."
        return response_text

    def _resolve_target_doc_id(self, job_id: str, user_message: str, workspace_context: dict[str, Any] | None) -> str:
        if not workspace_context:
            return job_id

        lowered = user_message.lower()
        for document in workspace_context.get("documents", []):
            document_id = document.get("id")
            filename = str(document.get("filename") or "").lower()
            if document_id and document_id.lower() in lowered:
                return document_id
            if filename and filename in lowered:
                return document_id or job_id
        return job_id

    def _extract_page_number(self, message: str) -> int | None:
        match = re.search(r"page\s+(\d+)", message, re.IGNORECASE)
        if not match:
            return None
        return int(match.group(1))

    def _extract_search_query(self, message: str) -> str:
        quoted = self.rule_engine._extract_quoted_text(message)
        if quoted:
            return quoted

        match = re.search(r"(?:search|find|look for|locate)\s+(?:for\s+)?(.+)$", message, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip("?.")
        return message.strip()

    def _extract_reason(self, message: str) -> str:
        match = re.search(r"(?:because|reason:?|due to)\s+(.+)$", message, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "Excluded from workspace automation"

    def _find_exclusion_for_doc(self, workspace_context: dict[str, Any] | None, document_id: str) -> dict[str, Any] | None:
        if not workspace_context:
            return None
        for exclusion in workspace_context.get("exclusions", []):
            if exclusion.get("document_id") == document_id:
                return exclusion
        return None

    def _is_workspace_state_request(self, lowered: str) -> bool:
        return any(
            keyword in lowered
            for keyword in (
                "workspace state",
                "workspace summary",
                "documents in workspace",
                "show workspace",
                "workspace rules",
                "workspace exclusions",
            )
        )

    def _tool_call(self, name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        return {"name": name, "arguments": args, "result": result}

    def _response(self, text: str, tool_calls: list[dict[str, Any]], directives: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "text": text,
            "response_id": str(uuid.uuid4()),
            "tool_calls": tool_calls,
            "directives": directives,
        }
