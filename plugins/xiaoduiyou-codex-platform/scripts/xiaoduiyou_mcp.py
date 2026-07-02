#!/usr/bin/env python3
"""MCP server exposing Xiaoduiyou Agent APIs to Codex."""

from __future__ import annotations

import json
import os
import base64
import hashlib
import secrets
import socket
import ssl
import struct
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from urllib import error, parse, request


VERSION = "0.1.5"
CONNECTOR_VERSION = "2026.7.3.1-codex"
DEFAULT_CONFIG_PATH = Path.home() / ".codex" / "xiaoduiyou-connection.json"


def _env(name: str, fallback: str) -> str:
    return os.environ.get(name, "").strip() or os.environ.get(fallback, "").strip()


def config_path() -> Path:
    override = os.environ.get("XIAODUIYOU_CODEX_CONFIG", "").strip()
    return Path(override).expanduser() if override else DEFAULT_CONFIG_PATH


def read_config() -> dict[str, str]:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        "base_url": str(payload.get("base_url") or payload.get("XDY_BASE_URL") or "").strip(),
        "connection_token": str(payload.get("connection_token") or payload.get("XDY_CONNECTION_TOKEN") or "").strip(),
    }


def write_config(origin: str, token: str) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"base_url": origin.rstrip("/"), "connection_token": token}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def base_url() -> str:
    return (_env("XDY_BASE_URL", "XIAODUIYOU_BASE_URL") or read_config().get("base_url", "")).rstrip("/")


def connection_token() -> str:
    return _env("XDY_CONNECTION_TOKEN", "XIAODUIYOU_CONNECTION_TOKEN") or read_config().get("connection_token", "")


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


class XiaoduiyouWebSocketError(RuntimeError):
    pass


def pending_turns_websocket_url() -> str:
    account = configured_account()
    parsed = parse.urlparse(account["base_url"])
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return parse.urlunparse((scheme, parsed.netloc, "/ws/agent/turns/pending", "", "", ""))


def interactive_request_websocket_url(request_id: str) -> str:
    account = configured_account()
    parsed = parse.urlparse(account["base_url"])
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = f"/ws/agent/interactive-requests/{parse.quote(request_id, safe='')}"
    return parse.urlunparse((scheme, parsed.netloc, path, "", "", ""))


def websocket_send_frame(sock: socket.socket, opcode: int, payload: bytes = b"") -> None:
    first = 0x80 | opcode
    mask = secrets.token_bytes(4)
    if len(payload) < 126:
        header = bytes([first, 0x80 | len(payload)])
    elif len(payload) < 65536:
        header = bytes([first, 0x80 | 126]) + struct.pack("!H", len(payload))
    else:
        header = bytes([first, 0x80 | 127]) + struct.pack("!Q", len(payload))
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    sock.sendall(header + mask + masked)


def websocket_read_exact(sock: socket.socket, length: int, buffer: bytearray) -> bytes:
    while len(buffer) < length:
        chunk = sock.recv(length - len(buffer))
        if not chunk:
            raise XiaoduiyouWebSocketError("websocket closed")
        buffer.extend(chunk)
    value = bytes(buffer[:length])
    del buffer[:length]
    return value


def websocket_read_text(sock: socket.socket, buffer: bytearray) -> str | None:
    header = websocket_read_exact(sock, 2, buffer)
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", websocket_read_exact(sock, 2, buffer))[0]
    elif length == 127:
        length = struct.unpack("!Q", websocket_read_exact(sock, 8, buffer))[0]
    payload = websocket_read_exact(sock, length, buffer) if length else b""
    if opcode == 8:
        raise XiaoduiyouWebSocketError("websocket closed by server")
    if opcode == 9:
        websocket_send_frame(sock, 0xA, payload)
        return None
    if opcode != 1:
        return None
    return payload.decode("utf-8")


def open_websocket_url(url: str, timeout: float) -> tuple[socket.socket, bytearray]:
    account = configured_account()
    parsed = parse.urlparse(url)
    host = parsed.hostname
    if not host:
        raise XiaoduiyouWebSocketError("websocket host is missing")
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    raw_sock = socket.create_connection((host, port), timeout=timeout)
    sock = ssl.create_default_context().wrap_socket(raw_sock, server_hostname=host) if parsed.scheme == "wss" else raw_sock
    sock.settimeout(timeout)
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    sock.sendall("\r\n".join([
        f"GET {parsed.path or '/'} HTTP/1.1",
        f"Host: {parsed.netloc}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
        f"Authorization: Bearer {account['connection_token']}",
        f"X-XDY-Connector-Version: {CONNECTOR_VERSION}",
        "X-XDY-Connector-Provider: codex",
        "",
        "",
    ]).encode("utf-8"))
    raw = b""
    while b"\r\n\r\n" not in raw:
        chunk = sock.recv(4096)
        if not chunk:
            raise XiaoduiyouWebSocketError("websocket closed during handshake")
        raw += chunk
    head, rest = raw.split(b"\r\n\r\n", 1)
    status_line, *header_lines = head.decode("iso-8859-1", errors="replace").split("\r\n")
    parts = status_line.split()
    status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if status == 401:
        sock.close()
        err = RuntimeError("UNAUTHENTICATED")
        setattr(err, "status", 401)
        raise err
    if status != 101:
        sock.close()
        raise XiaoduiyouWebSocketError(f"websocket upgrade failed: HTTP {status}")
    headers = {}
    for line in header_lines:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    expected_accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
    if headers.get("sec-websocket-accept") != expected_accept:
        sock.close()
        raise XiaoduiyouWebSocketError("websocket upgrade failed: bad Sec-WebSocket-Accept")
    return sock, bytearray(rest)


def open_pending_turns_websocket(timeout: float) -> tuple[socket.socket, bytearray]:
    return open_websocket_url(pending_turns_websocket_url(), timeout)


def claim_turn_via_websocket(timeout_seconds: float, *, wait_for_turn: bool = False) -> Any:
    sock, buffer = open_pending_turns_websocket(timeout_seconds)
    try:
        deadline = time.time() + timeout_seconds
        while time.time() <= deadline:
            sock.settimeout(max(0.5, min(5.0, deadline - time.time())))
            try:
                raw = websocket_read_text(sock, buffer)
            except socket.timeout:
                continue
            if not raw:
                continue
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("error"):
                if payload.get("error") == "UNAUTHENTICATED":
                    err = RuntimeError("UNAUTHENTICATED")
                    setattr(err, "status", 401)
                    raise err
                return payload
            if wait_for_turn and isinstance(payload, dict) and not payload.get("turn"):
                continue
            return payload
        return {"turn": None, "status": "NO_PENDING_TURN"}
    finally:
        try:
            websocket_send_frame(sock, 8)
        except Exception:
            pass
        sock.close()


def wait_interactive_request_via_websocket(request_id: str, timeout_seconds: float) -> Any:
    sock, buffer = open_websocket_url(interactive_request_websocket_url(request_id), timeout_seconds)
    try:
        deadline = time.time() + timeout_seconds
        attempts = 0
        while time.time() <= deadline:
            sock.settimeout(max(0.5, min(5.0, deadline - time.time())))
            try:
                raw = websocket_read_text(sock, buffer)
            except socket.timeout:
                continue
            if not raw:
                continue
            attempts += 1
            payload = json.loads(raw)
            request_payload = payload.get("request") if isinstance(payload, dict) else None
            if isinstance(request_payload, dict) and request_payload.get("status") in ("resolved", "expired"):
                return {"status": "DECISION_RECEIVED", "transport": "websocket", "attempts": attempts, "request": request_payload}
        return {"status": "NO_DECISION", "transport": "websocket", "attempts": attempts, "request_id": request_id}
    finally:
        try:
            websocket_send_frame(sock, 8)
        except Exception:
            pass
        sock.close()


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
            "config_path": str(config_path()),
            "source": "env" if _env("XDY_BASE_URL", "XIAODUIYOU_BASE_URL") or _env("XDY_CONNECTION_TOKEN", "XIAODUIYOU_CONNECTION_TOKEN") else "config",
        }
        if origin and token and args.get("probe"):
            status["probe"] = request_json("/api/agent/sessions")
        return text_result(status)

    if name == "xiaoduiyou_connection_configure":
        origin = required(args, "base_url").rstrip("/")
        token = required(args, "connection_token")
        if not origin.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        path = write_config(origin, token)
        return text_result({
            "configured": True,
            "base_url": origin,
            "has_connection_token": True,
            "config_path": str(path),
            "next_step": "Call xiaoduiyou_connection_status with probe=true, then xiaoduiyou_agent_turn_claim or xiaoduiyou_agent_turn_watch.",
        })

    if name == "xiaoduiyou_agent_turn_claim":
        try:
            return text_result(claim_turn_via_websocket(float(args.get("timeout_seconds") or 30)))
        except (RuntimeError, XiaoduiyouWebSocketError, OSError, json.JSONDecodeError) as exc:
            if isinstance(exc, RuntimeError) and getattr(exc, "status", None) not in (None, 404):
                raise
            try:
                return text_result(request_json("/api/agent/turns/pending"))
            except RuntimeError as http_exc:
                exc = http_exc
            if getattr(exc, "status", None) == 404:
                return text_result({"turn": None, "status": "NO_PENDING_TURN"})
            raise

    if name == "xiaoduiyou_agent_turn_watch":
        timeout_seconds = max(1.0, min(float(args.get("timeout_seconds") or 60), 300.0))
        try:
            result = claim_turn_via_websocket(timeout_seconds, wait_for_turn=True)
            if isinstance(result, dict) and result.get("turn"):
                return text_result({"status": "TURN_CLAIMED", "transport": "websocket", **result})
            return text_result(result)
        except (XiaoduiyouWebSocketError, OSError, json.JSONDecodeError):
            interval_seconds = max(0.5, min(float(args.get("interval_seconds") or 2), 10.0))
            deadline = time.time() + timeout_seconds
            attempts = 0
            last_error: dict[str, Any] | None = None
            while time.time() <= deadline:
                attempts += 1
                try:
                    result = request_json("/api/agent/turns/pending")
                    return text_result({"status": "TURN_CLAIMED", "transport": "http", "attempts": attempts, **(result if isinstance(result, dict) else {"result": result})})
                except RuntimeError as exc:
                    if getattr(exc, "status", None) != 404:
                        raise
                    last_error = {"status": getattr(exc, "status", None), "message": str(exc)}
                time.sleep(interval_seconds)
            return text_result({"turn": None, "status": "NO_PENDING_TURN", "attempts": attempts, "last_error": last_error})

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

    if name == "xiaoduiyou_agent_channels_list":
        return text_result(request_json("/api/agent/sessions"))

    if name == "xiaoduiyou_agent_channel_message":
        session_id = required(args, "session_id")
        body: dict[str, Any]
        if isinstance(args.get("payload"), dict):
            body = args["payload"]
        else:
            body = {"text": str(args.get("text") or "")}
        return text_result(request_json(f"/api/agent/sessions/{parse.quote(session_id)}/messages", method="POST", body=body))

    if name == "xiaoduiyou_im_send":
        session_id = str(args.get("session_id") or "").strip()
        channel = str(args.get("channel") or "default").strip()
        content = args.get("content")
        text = str(args.get("text") or "").strip()
        tool_progress = str(args.get("tool_progress") or "").strip()
        message_type = str(args.get("message_type") or "").strip()
        if (not isinstance(content, list) or not content) and not text and not tool_progress:
            raise ValueError("content[], text, or tool_progress is required")
        payload: dict[str, Any] = {}
        if isinstance(content, list) and content:
            payload["content"] = content
        if text:
            payload["text"] = text
        if tool_progress:
            payload["tool_progress"] = tool_progress
        if message_type in {"text", "tool_progress"}:
            payload["message_type"] = message_type
        if session_id:
            payload["session_id"] = session_id
        else:
            payload["channel"] = channel or "default"
        turn_id = str(args.get("turn_id") or "").strip()
        if turn_id:
            payload["turn_id"] = turn_id
        return text_result(request_json("/api/agent/im/send", method="POST", body=payload))

    if name == "xiaoduiyou_interactive_request_create":
        session_id = required(args, "session_id")
        kind = required(args, "kind")
        if kind not in ("exec_approval", "slash_confirm"):
            raise ValueError("kind must be exec_approval or slash_confirm")
        payload: dict[str, Any] = {"session_id": session_id, "kind": kind}
        for key in ["turn_id", "title", "message", "command", "reason", "confirm_id", "session_key"]:
            value = str(args.get(key) or "").strip()
            if value:
                payload[key] = value
        if isinstance(args.get("actions"), list):
            payload["actions"] = args["actions"]
        if args.get("timeout_seconds") is not None:
            payload["timeout_seconds"] = args["timeout_seconds"]
        return text_result(request_json("/api/agent/interactive-requests", method="POST", body=payload))

    if name == "xiaoduiyou_interactive_request_get":
        request_id = required(args, "request_id")
        return text_result(request_json(f"/api/agent/interactive-requests/{parse.quote(request_id)}"))

    if name == "xiaoduiyou_interactive_request_wait":
        request_id = required(args, "request_id")
        timeout_seconds = max(1.0, min(float(args.get("timeout_seconds") or 300), 600.0))
        interval_seconds = max(0.5, min(float(args.get("interval_seconds") or 1), 10.0))
        try:
            return text_result(wait_interactive_request_via_websocket(request_id, timeout_seconds))
        except Exception:
            pass
        deadline = time.time() + timeout_seconds
        attempts = 0
        while time.time() <= deadline:
            attempts += 1
            result = request_json(f"/api/agent/interactive-requests/{parse.quote(request_id)}")
            request_payload = result.get("request") if isinstance(result, dict) else None
            if isinstance(request_payload, dict) and request_payload.get("status") in ("resolved", "expired"):
                return text_result({"status": "DECISION_RECEIVED", "transport": "http", "attempts": attempts, "request": request_payload})
            time.sleep(interval_seconds)
        return text_result({"status": "NO_DECISION", "transport": "http", "attempts": attempts, "request_id": request_id})

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

    if name == "xiaoduiyou_child_get":
        allowed = ["session_id", "turn_id"]
        return text_result(request_json(f"/api/child{compact_query({key: args.get(key) for key in allowed})}"))

    if name == "xiaoduiyou_child_patch":
        profile = args.get("profile")
        skill_node_states = args.get("skill_node_states")
        payload: Dict[str, Any] = {}
        if profile is not None:
            if not isinstance(profile, dict):
                raise ValueError("profile must be a JSON object")
            payload["profile"] = profile
        if skill_node_states is not None:
            if not isinstance(skill_node_states, dict):
                raise ValueError("skill_node_states must be a JSON object")
            payload["skill_node_states"] = skill_node_states
        if not payload:
            raise ValueError("profile or skill_node_states is required")
        allowed = ["session_id", "turn_id"]
        return text_result(request_json(
            f"/api/child{compact_query({key: args.get(key) for key in allowed})}",
            method="PATCH",
            body=payload,
        ))

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
        if args.get("base_revision") is not None:
            payload["base_revision"] = int(args.get("base_revision") or 0)
        if args.get("allow_overwrite_after_patch") is not None:
            payload["allow_overwrite_after_patch"] = bool(args.get("allow_overwrite_after_patch"))
        if isinstance(args.get("blocks"), list):
            payload["blocks"] = args["blocks"]
        for key in ["platform", "index", "image_url", "caption", "history_caption", "sync_process_doc", "images", "columns"]:
            if key in args:
                payload[key] = args[key]
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
        "name": "xiaoduiyou_connection_configure",
        "description": "Persist Xiaoduiyou connection values from the app settings prompt so already-running Codex MCP processes can connect.",
        "inputSchema": schema({"base_url": {"type": "string"}, "connection_token": {"type": "string"}}, ["base_url", "connection_token"]),
    },
    {
        "name": "xiaoduiyou_agent_turn_claim",
        "description": "Claim the next pending Xiaoduiyou Agent turn for Codex.",
        "inputSchema": schema({}),
    },
    {
        "name": "xiaoduiyou_agent_turn_watch",
        "description": "Long-poll for a pending Xiaoduiyou turn and claim it when available. Use only while the Codex thread should stay actively connected.",
        "inputSchema": schema({"timeout_seconds": {"type": "number", "minimum": 1, "maximum": 300}, "interval_seconds": {"type": "number", "minimum": 0.5, "maximum": 10}}),
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
        "name": "xiaoduiyou_agent_channels_list",
        "description": "List Xiaoduiyou channels accessible to the current connection token. Results include internal session_id values only for targeting a specific active channel.",
        "inputSchema": schema({}),
    },
    {
        "name": "xiaoduiyou_agent_channel_message",
        "description": "Send an Agent message into a specific Xiaoduiyou channel by its internal session_id. Prefer xiaoduiyou_im_send with channel=default for background/Home delivery.",
        "inputSchema": schema({"session_id": {"type": "string"}, "text": {"type": "string"}, "payload": {"type": "object", "additionalProperties": True}}, ["session_id"]),
    },
    {
        "name": "xiaoduiyou_im_send",
        "description": "Send Xiaoduiyou chat text, tool-progress, or image cards to the Home default channel (主对话) or a specific session. Omit session_id for background/default delivery. Use input_text and input_image for cards; pass HTTPS or data:image/... base64 in image_url. Xiaoduiyou backend uploads images/assets. Never pass local paths, file:, blob:, localhost, or private-network URLs.",
        "inputSchema": schema({
            "channel": {"type": "string", "description": "Stable Xiaoduiyou Home channel key. Defaults to default/主对话 when session_id is omitted."},
            "session_id": {"type": "string"},
            "turn_id": {"type": "string"},
            "text": {"type": "string"},
            "message_type": {"type": "string", "enum": ["text", "tool_progress"]},
            "tool_progress": {"type": "string"},
            "content": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "type": {"type": "string", "enum": ["input_text", "input_image"]},
                        "text": {"type": "string"},
                        "image_url": {"type": "string", "description": "HTTPS URL or data:image/png|jpeg|webp|gif;base64,..."},
                        "detail": {"type": "string", "enum": ["auto", "low", "high"]},
                        "display": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "title": {"type": "string"},
                                "subtitle": {"type": "string"},
                                "badge": {"type": "string"},
                                "link_url": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }, ["content"]),
    },
    {
        "name": "xiaoduiyou_interactive_request_create",
        "description": "Create a Xiaoduiyou human authorization/confirmation card for the current chat. Use this when Codex needs user approval to execute a command or continue a slash/control action; do not ask for approval only in plain text.",
        "inputSchema": schema({
            "session_id": {"type": "string"},
            "turn_id": {"type": "string"},
            "kind": {"type": "string", "enum": ["exec_approval", "slash_confirm"]},
            "title": {"type": "string"},
            "message": {"type": "string"},
            "command": {"type": "string", "description": "Required context for exec_approval cards: the command or operation needing approval."},
            "reason": {"type": "string"},
            "confirm_id": {"type": "string"},
            "session_key": {"type": "string"},
            "actions": {
                "type": "array",
                "items": {"type": "string", "enum": ["once", "session", "always", "deny", "cancel"]},
            },
            "timeout_seconds": {"type": "number", "minimum": 15, "maximum": 3600},
        }, ["session_id", "kind"]),
    },
    {
        "name": "xiaoduiyou_interactive_request_get",
        "description": "Read the latest state of a Xiaoduiyou authorization/confirmation card. Returns pending, resolved, or expired plus the user's choice.",
        "inputSchema": schema({"request_id": {"type": "string"}}, ["request_id"]),
    },
    {
        "name": "xiaoduiyou_interactive_request_wait",
        "description": "Wait for a Xiaoduiyou authorization/confirmation card to be resolved. Use after create when the next Agent step depends on the user's approval choice.",
        "inputSchema": schema({
            "request_id": {"type": "string"},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "interval_seconds": {"type": "number", "minimum": 0.5, "maximum": 10},
        }, ["request_id"]),
    },
    {
        "name": "xiaoduiyou_child_get",
        "description": "Read Xiaoduiyou child profile and four-dimension development skill-node progress for the connected account. Use skill xiaoduiyou-child-profile before writes.",
        "inputSchema": schema({"session_id": {"type": "string"}, "turn_id": {"type": "string"}}),
    },
    {
        "name": "xiaoduiyou_child_patch",
        "description": "Patch Xiaoduiyou child profile and/or development skill-node states. Call xiaoduiyou_child_get first and send only explicitly provided profile fields or skill_node_states keys.",
        "inputSchema": schema({
            "profile": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "birthday": {"type": "string", "description": "YYYY-MM-DD"},
                    "gender": {"type": "string"},
                    "allergy": {"type": "string"},
                    "heightCm": {"type": "string"},
                    "weightKg": {"type": "string"},
                    "photoUrl": {"type": "string"},
                },
            },
            "skill_node_states": {
                "type": "object",
                "description": "Development skill-node state patch. Keys are returned by xiaoduiyou_child_get development[].nodes[].key, e.g. grossMotor:独走几步. Values are true for lit/unlocked and false for unlit/locked.",
                "additionalProperties": {"type": "boolean"},
            },
            "session_id": {"type": "string"},
            "turn_id": {"type": "string"},
        }),
    },
    {
        "name": "xiaoduiyou_growth_diary_get",
        "description": "Read Xiaoduiyou Growth Diary data. Use view=records with filters to find record_id values.",
        "inputSchema": schema({"view": {"type": "string", "enum": ["full", "records"]}, "date": {"type": "string"}, "start_date": {"type": "string"}, "end_date": {"type": "string"}, "event_type": {"type": "string"}, "query": {"type": "string"}, "quantity": {"type": "number"}, "unit": {"type": "string"}, "record_limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
    },
    {
        "name": "xiaoduiyou_growth_diary_patch",
        "description": "Patch Xiaoduiyou Growth Diary data. Call get first. New records must have records[].table_id/source at root and values under records[].values. For records with source='agent', values.date is required as YYYY-MM-DD and values.occurred_at is required as YYYY-MM-DD HH:mm:ss; short times like 19:20 are rejected, and occurred_at must use the same date as date.",
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
        "inputSchema": schema({"document_id": {"type": "string"}, "command": {"type": "string", "enum": ["overwrite", "append_blocks", "patch_fields", "replace_publish_image", "upsert_image_grid", "sync_publish_images_to_document"]}, "base_revision": {"type": "integer"}, "allow_overwrite_after_patch": {"type": "boolean"}, "title": {"type": "string"}, "body": {"type": "string"}, "markdown": {"type": "string"}, "block_json": {"type": "object", "additionalProperties": True}, "blocks": {"type": "array", "items": {"type": "object", "additionalProperties": True}}, "fields": {"type": "object", "additionalProperties": True}, "ui_templates": {"type": "array", "items": {"type": "string", "enum": ["xiaohongshu", "moments"]}}, "platform": {"type": "string"}, "index": {"type": "integer"}, "image_url": {"type": "string"}, "caption": {"type": "string"}, "history_caption": {"type": "string"}, "sync_process_doc": {"type": "boolean"}, "images": {"type": "array", "items": {"type": "object", "additionalProperties": True}}, "columns": {"type": "integer"}}, ["document_id"]),
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
