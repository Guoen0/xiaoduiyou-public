#!/usr/bin/env python3
"""MCP server exposing Xiaoduiyou Agent APIs to Codex."""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any
from urllib import error, parse, request


VERSION = "0.1.0"
CONNECTOR_VERSION = "2026.6.3.4-codex.0"


def _env(name: str, fallback: str) -> str:
    return os.environ.get(name, "").strip() or os.environ.get(fallback, "").strip()


def base_url() -> str:
    return _env("XDY_BASE_URL", "XIAODUIYOU_BASE_URL").rstrip("/")


def connection_token() -> str:
    return _env("XDY_CONNECTION_TOKEN", "XIAODUIYOU_CONNECTION_TOKEN")


def configured_account() -> dict[str, str]:
    origin = base_url()
    token = connection_token()
    if not origin or not token:
        missing = []
        if not origin:
            missing.append("XDY_BASE_URL")
        if not token:
            missing.append("XDY_CONNECTION_TOKEN")
        raise ValueError(f"Missing Xiaoduiyou connection env: {', '.join(missing)}")
    return {"base_url": origin, "connection_token": token}


def compact_query(params: dict[str, Any]) -> str:
    clean = {key: str(value) for key, value in params.items() if value not in (None, "")}
    return f"?{parse.urlencode(clean)}" if clean else ""


def request_json(path: str, *, method: str = "GET", body: Any = None, headers: dict[str, str] | None = None) -> Any:
    account = configured_account()
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{account['base_url']}{path}",
        method=method,
        data=data,
        headers={
            "authorization": f"Bearer {account['connection_token']}",
            "content-type": "application/json",
            "x-xdy-connector-version": CONNECTOR_VERSION,
            "x-xdy-connector-provider": "codex",
            **(headers or {}),
        },
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw or f"HTTP_{exc.code}"}
        message = payload.get("error") if isinstance(payload, dict) else None
        err = RuntimeError(str(message or f"HTTP_{exc.code}"))
        setattr(err, "status", exc.code)
        setattr(err, "payload", payload)
        raise err


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def text_result(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json_text(value)}], "isError": is_error}


def block_json_from_text(title: str, body: str) -> dict[str, Any]:
    blocks = []
    clean_title = str(title or "").strip()
    if clean_title:
        blocks.append({"type": "heading", "props": {"level": 2}, "content": [{"type": "text", "text": clean_title, "styles": {}}]})
    for line in str(body or "").splitlines():
        text = line.strip()
        if text:
            blocks.append({"type": "paragraph", "content": [{"type": "text", "text": text, "styles": {}}]})
    return {"schema": "xdy.block_json.v1", "blocks": blocks}


def normalize_document_input(args: dict[str, Any], *, create: bool) -> dict[str, Any]:
    title = str(args.get("title") or ("Untitled" if create else "")).strip()
    body = str(args.get("body") or args.get("markdown") or "")
    block_json = args.get("block_json")
    if not isinstance(block_json, dict) or not isinstance(block_json.get("blocks"), list):
        block_json = block_json_from_text(title, body)
    payload: dict[str, Any] = {"block_json": block_json}
    if title:
        payload["title"] = title
    fields = args.get("fields")
    if isinstance(fields, dict):
        payload["fields"] = fields
    if isinstance(args.get("ui_templates"), list):
        payload.setdefault("fields", {})["ui_templates"] = [value for value in args["ui_templates"] if value in ("xiaohongshu", "moments")]
    return payload


def growth_diary_patch_failure(error_value: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "message": str(error_value),
            "status": getattr(error_value, "status", None),
            "payload": getattr(error_value, "payload", None),
        },
        "skill": "xiaoduiyou-growth-diary",
        "hint": "Read/use skill xiaoduiyou-growth-diary, then retry with payload.records[].table_id and source at the record root, and field values inside records[].values. Use updates for existing cells and deletions for deletes.",
    }


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "xiaoduiyou_connection_status":
        origin = base_url()
        token = connection_token()
        status: dict[str, Any] = {
            "configured": bool(origin and token),
            "base_url": origin or None,
            "has_connection_token": bool(token),
            "connector_provider": "codex",
            "connector_version": CONNECTOR_VERSION,
        }
        if origin and token and args.get("probe"):
            status["probe"] = request_json("/api/agent/sessions")
        return text_result(status)

    if name == "xiaoduiyou_agent_turn_claim":
        try:
            return text_result(request_json("/api/agent/turns/pending"))
        except RuntimeError as exc:
            if getattr(exc, "status", None) == 404:
                return text_result({"turn": None, "status": "NO_PENDING_TURN"})
            raise

    if name == "xiaoduiyou_agent_turn_progress":
        turn_id = required(args, "turn_id")
        body: dict[str, Any] = {}
        if args.get("progress") is not None:
            body["progress"] = args["progress"]
        if args.get("tool_progress") is not None:
            body["tool_progress"] = args["tool_progress"]
        if not body:
            raise ValueError("progress or tool_progress is required")
        return text_result(request_json(f"/api/agent/turns/{parse.quote(turn_id)}/events", method="POST", body=body))

    if name == "xiaoduiyou_agent_turn_complete":
        turn_id = required(args, "turn_id")
        body = {"progress": args.get("progress") or "Codex has completed this Xiaoduiyou turn."}
        if args.get("artifact") is not None:
            body["artifact"] = args["artifact"]
        if isinstance(args.get("document_actions"), list):
            body["document_actions"] = args["document_actions"]
        return text_result(request_json(f"/api/agent/turns/{parse.quote(turn_id)}/callback", method="POST", body=body))

    if name == "xiaoduiyou_agent_turn_fail":
        turn_id = required(args, "turn_id")
        return text_result(request_json(f"/api/agent/turns/{parse.quote(turn_id)}/failure", method="POST", body={"error": required(args, "error")}))

    if name == "xiaoduiyou_agent_sessions_list":
        return text_result(request_json("/api/agent/sessions"))

    if name == "xiaoduiyou_agent_session_message":
        session_id = required(args, "session_id")
        body: dict[str, Any]
        if isinstance(args.get("payload"), dict):
            body = args["payload"]
        else:
            body = {"text": str(args.get("text") or "")}
        return text_result(request_json(f"/api/agent/sessions/{parse.quote(session_id)}/messages", method="POST", body=body))

    if name == "xiaoduiyou_growth_diary_get":
        allowed = ["view", "date", "start_date", "end_date", "event_type", "query", "quantity", "unit", "record_limit"]
        return text_result(request_json(f"/api/growth-diary{compact_query({key: args.get(key) for key in allowed})}"))

    if name == "xiaoduiyou_growth_diary_patch":
        payload = args.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        try:
            return text_result(request_json("/api/growth-diary", method="PATCH", body=payload))
        except Exception as exc:
            return text_result(growth_diary_patch_failure(exc), is_error=True)

    if name == "xiaoduiyou_documents_get":
        query = compact_query({key: args.get(key) for key in ["view", "field", "start", "block_limit", "char_limit"]})
        document_id = str(args.get("document_id") or "").strip()
        session_id = str(args.get("session_id") or "").strip()
        if document_id:
            return text_result(request_json(f"/api/docs/{parse.quote(document_id)}{query}"))
        if session_id:
            return text_result(request_json(f"/api/sessions/{parse.quote(session_id)}/document{query}"))
        raise ValueError("document_id or session_id is required")

    if name == "xiaoduiyou_documents_create":
        payload = normalize_document_input(args, create=True)
        payload["created_by"] = args.get("created_by") or "codex"
        return text_result(request_json("/api/docs", method="POST", body=payload))

    if name == "xiaoduiyou_documents_update":
        document_id = required(args, "document_id")
        payload = normalize_document_input(args, create=False)
        payload["command"] = args.get("command") or "overwrite"
        payload["updated_by"] = args.get("updated_by") or "codex"
        if isinstance(args.get("blocks"), list):
            payload["blocks"] = args["blocks"]
        return text_result(request_json(f"/api/docs/{parse.quote(document_id)}", method="PATCH", body=payload))

    if name == "xiaoduiyou_documents_delete":
        document_id = required(args, "document_id")
        return text_result(request_json(f"/api/drive/files/{parse.quote(document_id)}", method="DELETE"))

    if name == "xiaoduiyou_documents_export":
        document_id = required(args, "document_id")
        fmt = "json" if args.get("format") == "json" else "markdown"
        account = configured_account()
        req = request.Request(
            f"{account['base_url']}/api/docs/{parse.quote(document_id)}/export?format={fmt}",
            headers={
                "authorization": f"Bearer {account['connection_token']}",
                "x-xdy-connector-version": CONNECTOR_VERSION,
                "x-xdy-connector-provider": "codex",
            },
        )
        with request.urlopen(req, timeout=30) as resp:
            return {"content": [{"type": "text", "text": resp.read().decode("utf-8")}], "isError": False}

    raise ValueError(f"Unknown tool: {name}")


def required(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def schema(properties: dict[str, Any], required_fields: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": required_fields or []}


TOOLS = [
    {
        "name": "xiaoduiyou_connection_status",
        "description": "Check whether the Xiaoduiyou MCP server has connection env configured. Set probe=true to call the platform.",
        "inputSchema": schema({"probe": {"type": "boolean"}}),
    },
    {
        "name": "xiaoduiyou_agent_turn_claim",
        "description": "Claim the next pending Xiaoduiyou Agent turn for Codex.",
        "inputSchema": schema({}),
    },
    {
        "name": "xiaoduiyou_agent_turn_progress",
        "description": "Post visible progress or tool progress for an active Xiaoduiyou Agent turn.",
        "inputSchema": schema({"turn_id": {"type": "string"}, "progress": {"type": "string"}, "tool_progress": {"type": "string"}}, ["turn_id"]),
    },
    {
        "name": "xiaoduiyou_agent_turn_complete",
        "description": "Complete a Xiaoduiyou Agent turn. Include document_actions only when the user explicitly requested document mutation.",
        "inputSchema": schema({"turn_id": {"type": "string"}, "progress": {"type": "string"}, "artifact": {"type": "object", "additionalProperties": True}, "document_actions": {"type": "array", "items": {"type": "object", "additionalProperties": True}}}, ["turn_id"]),
    },
    {
        "name": "xiaoduiyou_agent_turn_fail",
        "description": "Fail an active Xiaoduiyou Agent turn with an error message.",
        "inputSchema": schema({"turn_id": {"type": "string"}, "error": {"type": "string"}}, ["turn_id", "error"]),
    },
    {
        "name": "xiaoduiyou_agent_sessions_list",
        "description": "List Xiaoduiyou sessions accessible to the current connection token.",
        "inputSchema": schema({}),
    },
    {
        "name": "xiaoduiyou_agent_session_message",
        "description": "Send an Agent message into a Xiaoduiyou session.",
        "inputSchema": schema({"session_id": {"type": "string"}, "text": {"type": "string"}, "payload": {"type": "object", "additionalProperties": True}}, ["session_id"]),
    },
    {
        "name": "xiaoduiyou_growth_diary_get",
        "description": "Read Xiaoduiyou Growth Diary data. Use view=records with filters to find record_id values.",
        "inputSchema": schema({"view": {"type": "string", "enum": ["full", "records"]}, "date": {"type": "string"}, "start_date": {"type": "string"}, "end_date": {"type": "string"}, "event_type": {"type": "string"}, "query": {"type": "string"}, "quantity": {"type": "number"}, "unit": {"type": "string"}, "record_limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
    },
    {
        "name": "xiaoduiyou_growth_diary_patch",
        "description": "Patch Xiaoduiyou Growth Diary data. Call get first. New records must have records[].table_id/source at root and values under records[].values.",
        "inputSchema": schema({"payload": {"type": "object", "additionalProperties": True}}, ["payload"]),
    },
    {
        "name": "xiaoduiyou_documents_get",
        "description": "Read a Xiaoduiyou document by document_id or a session's attached document by session_id.",
        "inputSchema": schema({"document_id": {"type": "string"}, "session_id": {"type": "string"}, "view": {"type": "string", "enum": ["summary", "field", "blocks", "full"]}, "field": {"type": "string"}, "start": {"type": "integer", "minimum": 0}, "block_limit": {"type": "integer", "minimum": 1, "maximum": 100}, "char_limit": {"type": "integer", "minimum": 200, "maximum": 20000}}),
    },
    {
        "name": "xiaoduiyou_documents_create",
        "description": "Create a Xiaoduiyou document only when the user explicitly asks for a document artifact.",
        "inputSchema": schema({"title": {"type": "string"}, "body": {"type": "string"}, "markdown": {"type": "string"}, "block_json": {"type": "object", "additionalProperties": True}, "fields": {"type": "object", "additionalProperties": True}, "ui_templates": {"type": "array", "items": {"type": "string", "enum": ["xiaohongshu", "moments"]}}}, ["title"]),
    },
    {
        "name": "xiaoduiyou_documents_update",
        "description": "Update a Xiaoduiyou document by document_id.",
        "inputSchema": schema({"document_id": {"type": "string"}, "command": {"type": "string", "enum": ["overwrite", "append_blocks", "patch_fields"]}, "title": {"type": "string"}, "body": {"type": "string"}, "markdown": {"type": "string"}, "block_json": {"type": "object", "additionalProperties": True}, "blocks": {"type": "array", "items": {"type": "object", "additionalProperties": True}}, "fields": {"type": "object", "additionalProperties": True}, "ui_templates": {"type": "array", "items": {"type": "string", "enum": ["xiaohongshu", "moments"]}}}, ["document_id"]),
    },
    {
        "name": "xiaoduiyou_documents_delete",
        "description": "Delete a Xiaoduiyou document by document_id.",
        "inputSchema": schema({"document_id": {"type": "string"}}, ["document_id"]),
    },
    {
        "name": "xiaoduiyou_documents_export",
        "description": "Export a Xiaoduiyou document as markdown or JSON.",
        "inputSchema": schema({"document_id": {"type": "string"}, "format": {"type": "string", "enum": ["markdown", "json"]}}, ["document_id"]),
    },
]


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "xiaoduiyou", "version": VERSION},
                },
            }
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
        if method == "tools/call":
            params = message.get("params") or {}
            result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32000,
                "message": str(exc),
                "data": traceback.format_exc(limit=4),
            },
        }


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
