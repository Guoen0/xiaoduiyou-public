#!/usr/bin/env python3
"""Send Xiaoduiyou visual cards via /api/agent/im/send.

Use this instead of MEDIA:/... or Markdown images when a Xiaoduiyou user asks for
视觉卡片. It sends OpenAI Responses-style content parts to the Home default
channel (shown to users as 主对话) unless --session-id targets a specific active session.
"""
from __future__ import annotations

import argparse, base64, json, mimetypes, os, re, tempfile, urllib.error, urllib.request
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


def list_channels(base: str, tok: str) -> list[dict[str, Any]]:
    data = request_json(f"{base}/api/agent/sessions", tok=tok)
    sessions = data.get("sessions")
    return [s for s in sessions if isinstance(s, dict)] if isinstance(sessions, list) else []


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
    p.add_argument("--channel", default="default", help="Stable Xiaoduiyou Home channel key. Defaults to default/主对话. Ignored when --session-id is set.")
    p.add_argument("--session-id")
    p.add_argument("--text", default="视觉卡片")
    p.add_argument("--cards-json", help="JSON array or path. Each card needs image_path or image_url plus title/link_url/subtitle/badge.")
    p.add_argument("--list-channels", action="store_true")
    p.add_argument("--allow-local-storage", action="store_true", help="Deprecated compatibility flag; /api/agent/im/send owns final asset storage.")
    args = p.parse_args()
    base, tok = base_url(args.base_url), token(args.token)
    if args.list_channels:
        print(json.dumps({"base_url": base, "channels": list_channels(base, tok)}, ensure_ascii=False, indent=2))
        return 0
    if not args.cards_json:
        raise SystemExit("Pass --cards-json")
    content: list[dict[str, Any]] = [{"type": "input_text", "text": args.text}]
    temps = []
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
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            if not mime.startswith("image/"):
                raise SystemExit(f"not an image file: {path}")
            display = {k: item[k] for k in ("title", "subtitle", "badge", "link_url") if item.get(k)}
            content.append({
                "type": "input_image",
                "image_url": f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}",
                "detail": "auto",
                "display": display,
            })
        payload = {"content": content}
        if args.session_id:
            payload["session_id"] = args.session_id
        else:
            payload["channel"] = args.channel or "default"
        result = request_json(f"{base}/api/agent/im/send", method="POST", tok=tok, payload=payload)
        event = result.get("event") or {}; ep = event.get("payload") or {}
        target = result.get("target") or {}
        print(json.dumps({"status": result.get("status"), "message_id": result.get("message_id"), "target": target, "session_id": event.get("session_id"), "event_type": event.get("type"), "attachment_count": len(ep.get("image_attachments") or [])}, ensure_ascii=False, indent=2))
        return 0
    finally:
        for t in temps:
            try: t.unlink()
            except OSError: pass

if __name__ == "__main__":
    raise SystemExit(main())
