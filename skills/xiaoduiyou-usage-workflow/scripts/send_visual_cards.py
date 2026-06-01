#!/usr/bin/env python3
"""Send Xiaoduiyou visual cards through the real session-message API.

This script is for connected Agents that need to deliver clickable image cards to
Xiaoduiyou chat. It uploads local/remote images to `/api/assets` first, then posts
`image_attachments` to `/api/agent/sessions/:session_id/messages`.

Examples:
  python scripts/send_visual_cards.py --list-sessions
  python scripts/send_visual_cards.py --session-id sess_0005 --text '参考卡片' \
    --card '{"image_path":"/tmp/card.png","title":"龙柳参考","link_url":"https://www.xiaohongshu.com/explore/...","badge":"参考帖"}'
  python scripts/send_visual_cards.py --session-id sess_0005 --cards-json /tmp/cards.json
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PLUGIN_VERSION = "2026.6.1"
DEFAULT_TIMEOUT = 45


def _load_config() -> dict[str, Any]:
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    config_path = home / "config.yaml"
    if not config_path.exists():
        return {}
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        loaded = yaml.safe_load(text) or {}
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        result: dict[str, Any] = {"platforms": {"xiaoduiyou": {"extra": {}}}}
        for key in ("base_url", "connection_token", "token"):
            match = re.search(rf"^\s*{re.escape(key)}\s*:\s*['\"]?([^'\"\n]+)", text, re.M)
            if match:
                result["platforms"]["xiaoduiyou"]["extra"][key] = match.group(1).strip()
        return result


def _config_extra() -> dict[str, Any]:
    cfg = _load_config()
    platform = ((cfg.get("platforms") or {}).get("xiaoduiyou") or {}) if isinstance(cfg, dict) else {}
    extra = platform.get("extra") or {}
    return extra if isinstance(extra, dict) else {}


def resolve_base_url(explicit: str | None) -> str:
    value = explicit or os.environ.get("XIAODUIYOU_BASE_URL") or os.environ.get("XDY_BASE_URL") or _config_extra().get("base_url") or "http://localhost:5173"
    return str(value).rstrip("/")


def resolve_token(explicit: str | None) -> str:
    value = explicit or os.environ.get("XIAODUIYOU_CONNECTION_TOKEN") or os.environ.get("XDY_CONNECTION_TOKEN") or _config_extra().get("connection_token") or _config_extra().get("token") or ""
    if not value:
        raise SystemExit("Missing Xiaoduiyou Agent token. Set XDY_CONNECTION_TOKEN or configure platforms.xiaoduiyou.extra.connection_token.")
    return str(value)


def request_json(url: str, *, method: str = "GET", token: str = "", payload: Any = None, headers: dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    body = None
    req_headers = {
        "Accept": "application/json",
        "X-XDY-Connector-Provider": "hermes",
        "X-XDY-Connector-Version": PLUGIN_VERSION,
    }
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {raw}") from exc


def list_sessions(base_url: str, token: str) -> list[dict[str, Any]]:
    data = request_json(f"{base_url}/api/agent/sessions", token=token)
    sessions = data.get("sessions")
    return [s for s in sessions if isinstance(s, dict)] if isinstance(sessions, list) else []


def resolve_session_id(base_url: str, token: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    env_value = os.environ.get("XIAODUIYOU_SESSION_ID") or os.environ.get("XDY_SESSION_ID")
    if env_value:
        return env_value
    sessions = list_sessions(base_url, token)
    if len(sessions) == 1 and sessions[0].get("session_id"):
        return str(sessions[0]["session_id"])
    for session in sessions:
        if session.get("session_purpose") == "floating_agent" and session.get("session_id"):
            return str(session["session_id"])
    raise SystemExit("Missing --session-id and could not choose a unique Xiaoduiyou session. Run with --list-sessions.")


def download_remote_image(url: str) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "Xiaoduiyou-Agent-VisualCards/1.0", "Referer": "https://www.xiaohongshu.com/"})
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        content_type = str(resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            raise RuntimeError(f"Remote URL is not an image: {url} ({content_type})")
        suffix = mimetypes.guess_extension(content_type) or ".img"
        fd, name = tempfile.mkstemp(prefix="xdy-card-", suffix=suffix)
        with os.fdopen(fd, "wb") as out:
            out.write(resp.read())
    return Path(name)


def upload_asset(base_url: str, token: str, session_id: str, file_path: Path, *, require_remote_storage: bool = True) -> str:
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    boundary = f"----XiaoduiyouVisualCard{int(time.time() * 1000)}"
    filename = file_path.name
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    fields = {"source": "agent_generated", "require_remote_storage": "true" if require_remote_storage else "false", "session_id": session_id}
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    chunks.append(f"Content-Type: {mime_type}\r\n\r\n".encode())
    chunks.append(file_path.read_bytes())
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"{base_url}/api/assets", data=b"".join(chunks), method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json", "X-XDY-Connector-Provider": "hermes", "X-XDY-Connector-Version": PLUGIN_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Asset upload failed HTTP {exc.code}: {raw}") from exc
    url = str(data.get("url") or ((data.get("asset") or {}).get("public_url")) or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError(f"Asset upload did not return public URL: {data}")
    return url


def load_cards(args: argparse.Namespace) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if args.cards_json:
        source = Path(args.cards_json)
        raw = source.read_text(encoding="utf-8") if source.exists() else args.cards_json
        loaded = json.loads(raw)
        if not isinstance(loaded, list):
            raise SystemExit("--cards-json must be a JSON array or a path to a JSON array file")
        cards.extend([c for c in loaded if isinstance(c, dict)])
    for raw_card in args.card or []:
        loaded = json.loads(raw_card)
        if not isinstance(loaded, dict):
            raise SystemExit("Each --card must be a JSON object")
        cards.append(loaded)
    if not cards:
        raise SystemExit("Provide at least one --card or --cards-json")
    return cards


def prepare_cards(base_url: str, token: str, session_id: str, cards: list[dict[str, Any]], *, require_remote_storage: bool = True) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    temp_paths: list[Path] = []
    try:
        for index, card in enumerate(cards, start=1):
            next_card = dict(card)
            image_path = str(next_card.pop("image_path", "") or "").strip()
            image_url = str(next_card.get("image_url") or next_card.get("url") or "").strip()
            if image_path:
                next_card["image_url"] = upload_asset(base_url, token, session_id, Path(image_path).expanduser(), require_remote_storage=require_remote_storage)
            elif image_url.startswith(("http://", "https://")):
                tmp = download_remote_image(image_url)
                temp_paths.append(tmp)
                next_card["image_url"] = upload_asset(base_url, token, session_id, tmp, require_remote_storage=require_remote_storage)
            else:
                raise SystemExit(f"Card #{index} missing image_path or image_url")
            if "badge" not in next_card:
                next_card["badge"] = "参考"
            prepared.append(next_card)
        return prepared
    finally:
        for path in temp_paths:
            try:
                path.unlink()
            except OSError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Send Xiaoduiyou visual cards via /api/assets + /api/agent/sessions/:id/messages")
    parser.add_argument("--base-url")
    parser.add_argument("--token")
    parser.add_argument("--session-id")
    parser.add_argument("--text", default="")
    parser.add_argument("--detail", default="")
    parser.add_argument("--card", action="append", help="JSON object. Use image_path or image_url plus title/link_url/subtitle/badge.")
    parser.add_argument("--cards-json", help="Path to JSON array or inline JSON array.")
    parser.add_argument("--list-sessions", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-local-storage", action="store_true", help="Allow app-local asset URLs when remote/TOS storage is not configured. Use only for review/local smoke tests.")
    args = parser.parse_args()
    base_url = resolve_base_url(args.base_url)
    token = resolve_token(args.token)
    if args.list_sessions:
        print(json.dumps({"base_url": base_url, "sessions": list_sessions(base_url, token)}, ensure_ascii=False, indent=2))
        return 0
    session_id = resolve_session_id(base_url, token, args.session_id)
    attachments = prepare_cards(base_url, token, session_id, load_cards(args), require_remote_storage=not args.allow_local_storage)
    image_urls = [card["image_url"] for card in attachments]
    payload = {"text": args.text or args.detail or "视觉卡片", "detail": args.detail or args.text or "视觉卡片", "image_urls": image_urls, "image_attachments": attachments}
    if args.dry_run:
        print(json.dumps({"base_url": base_url, "session_id": session_id, "payload": payload}, ensure_ascii=False, indent=2))
        return 0
    result = request_json(f"{base_url}/api/agent/sessions/{session_id}/messages", method="POST", token=token, payload=payload)
    event = result.get("event") or {}
    event_payload = event.get("payload") if isinstance(event, dict) else {}
    print(json.dumps({"status": result.get("status"), "message_id": result.get("message_id"), "session_id": event.get("session_id"), "event_type": event.get("type"), "attachment_count": len((event_payload or {}).get("image_attachments") or []), "image_urls": (event_payload or {}).get("image_urls") or []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
