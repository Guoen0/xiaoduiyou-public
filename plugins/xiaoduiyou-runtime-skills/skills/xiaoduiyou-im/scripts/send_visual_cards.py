#!/usr/bin/env python3
"""Send Xiaoduiyou visual cards via assets + structured image_attachments.

Use this instead of MEDIA:/... or Markdown images when a Xiaoduiyou user asks for
视觉卡片. It uploads local/remote images to /api/assets, then posts a structured
message to /api/agent/sessions/{session_id}/messages.
"""
from __future__ import annotations

import argparse, json, mimetypes, os, re, tempfile, time, urllib.error, urllib.request
from pathlib import Path
from typing import Any

VERSION = "2026.6.1"
TIMEOUT = 45


def load_config() -> dict[str, Any]:
    path = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "config.yaml"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        value = yaml.safe_load(text) or {}
        return value if isinstance(value, dict) else {}
    except Exception:
        extra: dict[str, str] = {}
        for key in ("base_url", "connection_token", "token"):
            m = re.search(rf"^\s*{re.escape(key)}\s*:\s*['\"]?([^'\"\n]+)", text, re.M)
            if m:
                extra[key] = m.group(1).strip()
        return {"platforms": {"xiaoduiyou": {"extra": extra}}}


def config_extra() -> dict[str, Any]:
    return (((load_config().get("platforms") or {}).get("xiaoduiyou") or {}).get("extra") or {})


def base_url(arg: str | None) -> str:
    return str(arg or os.getenv("XIAODUIYOU_BASE_URL") or os.getenv("XDY_BASE_URL") or config_extra().get("base_url") or "http://localhost:5173").rstrip("/")


def token(arg: str | None) -> str:
    value = arg or os.getenv("XIAODUIYOU_CONNECTION_TOKEN") or os.getenv("XDY_CONNECTION_TOKEN") or config_extra().get("connection_token") or config_extra().get("token")
    if not value:
        raise SystemExit("Missing token: set XDY_CONNECTION_TOKEN or platforms.xiaoduiyou.extra.connection_token")
    return str(value)


def request_json(url: str, *, method: str = "GET", tok: str, payload: Any = None) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {tok}",
        "X-XDY-Connector-Provider": "hermes",
        "X-XDY-Connector-Version": VERSION,
    }
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} {url}: {exc.read().decode('utf-8', 'replace')}") from exc


def list_sessions(base: str, tok: str) -> list[dict[str, Any]]:
    data = request_json(f"{base}/api/agent/sessions", tok=tok)
    sessions = data.get("sessions")
    return [s for s in sessions if isinstance(s, dict)] if isinstance(sessions, list) else []


def resolve_session(base: str, tok: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.getenv("XIAODUIYOU_SESSION_ID") or os.getenv("XDY_SESSION_ID")
    if env:
        return env
    sessions = list_sessions(base, tok)
    if len(sessions) == 1 and sessions[0].get("session_id"):
        return str(sessions[0]["session_id"])
    raise SystemExit("Pass --session-id (or run --list-sessions).")


def download_image(url: str) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "Xiaoduiyou-VisualCards/1.0", "Referer": "https://www.xiaohongshu.com/"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        ctype = str(resp.headers.get("content-type") or "").split(";")[0].lower()
        if not ctype.startswith("image/"):
            raise RuntimeError(f"not an image: {url} ({ctype})")
        suffix = mimetypes.guess_extension(ctype) or ".img"
        fd, name = tempfile.mkstemp(prefix="xdy-card-", suffix=suffix)
        with os.fdopen(fd, "wb") as f:
            f.write(resp.read())
        return Path(name)


def upload_asset(base: str, tok: str, session_id: str, file_path: Path, *, require_remote: bool) -> str:
    boundary = f"----XDYVisualCard{int(time.time() * 1000)}"
    filename = file_path.name
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    fields = {"source": "agent_generated", "session_id": session_id, "require_remote_storage": "true" if require_remote else "false"}
    chunks: list[bytes] = []
    for k, v in fields.items():
        chunks += [f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()]
    chunks += [f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(), f"Content-Type: {mime}\r\n\r\n".encode(), file_path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()]
    req = urllib.request.Request(f"{base}/api/assets", data=b"".join(chunks), method="POST", headers={"Authorization": f"Bearer {tok}", "Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json", "X-XDY-Connector-Provider": "hermes", "X-XDY-Connector-Version": VERSION})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"asset upload HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc
    url = str(data.get("url") or ((data.get("asset") or {}).get("public_url")) or "")
    if not url.startswith(("http://", "https://")):
        raise RuntimeError(f"asset upload returned no public URL: {data}")
    return url


def load_cards(value: str) -> list[dict[str, Any]]:
    raw = Path(value).read_text(encoding="utf-8") if Path(value).exists() else value
    cards = json.loads(raw)
    if not isinstance(cards, list):
        raise SystemExit("cards must be a JSON array")
    return [c for c in cards if isinstance(c, dict)]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url")
    p.add_argument("--token")
    p.add_argument("--session-id")
    p.add_argument("--text", default="视觉卡片")
    p.add_argument("--cards-json", help="JSON array or path. Each card needs image_path or image_url plus title/link_url/subtitle/badge.")
    p.add_argument("--list-sessions", action="store_true")
    p.add_argument("--allow-local-storage", action="store_true", help="Use only for local/review when TOS is not configured.")
    args = p.parse_args()
    base, tok = base_url(args.base_url), token(args.token)
    if args.list_sessions:
        print(json.dumps({"base_url": base, "sessions": list_sessions(base, tok)}, ensure_ascii=False, indent=2))
        return 0
    sid = resolve_session(base, tok, args.session_id)
    if not args.cards_json:
        raise SystemExit("Pass --cards-json")
    attachments, temps = [], []
    try:
        for card in load_cards(args.cards_json):
            item = dict(card)
            image_path = item.pop("image_path", "")
            image_url = item.get("image_url") or item.get("url")
            if image_path:
                path = Path(str(image_path)).expanduser()
            elif isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
                path = download_image(image_url); temps.append(path)
            else:
                raise SystemExit("each card needs image_path or image_url")
            item["image_url"] = upload_asset(base, tok, sid, path, require_remote=not args.allow_local_storage)
            item.setdefault("badge", "参考")
            attachments.append(item)
        payload = {"text": args.text, "detail": args.text, "image_urls": [a["image_url"] for a in attachments], "image_attachments": attachments}
        result = request_json(f"{base}/api/agent/sessions/{sid}/messages", method="POST", tok=tok, payload=payload)
        event = result.get("event") or {}; ep = event.get("payload") or {}
        print(json.dumps({"status": result.get("status"), "message_id": result.get("message_id"), "session_id": event.get("session_id"), "event_type": event.get("type"), "attachment_count": len(ep.get("image_attachments") or [])}, ensure_ascii=False, indent=2))
        return 0
    finally:
        for t in temps:
            try: t.unlink()
            except OSError: pass

if __name__ == "__main__":
    raise SystemExit(main())
