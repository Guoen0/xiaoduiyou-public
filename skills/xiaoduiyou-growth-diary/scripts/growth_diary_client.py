#!/usr/bin/env python3
"""Small Xiaoduiyou Growth Diary helper.

Uses the same config conventions as Xiaoduiyou IM scripts:
- prefer the active turn runtime origin when exported as XDY_RUNTIME_BASE_URL / XIAODUIYOU_RUNTIME_BASE_URL
- otherwise base_url from explicit --base-url, XDY/XIAODUIYOU env vars, or platforms.xiaoduiyou.extra.base_url
- connection token from explicit --token, XDY/XIAODUIYOU env vars, or platforms.xiaoduiyou.extra.connection_token

Do not rely on a stale local config when the active Xiaoduiyou turn came from a different product environment.

Examples:
  growth_diary_client.py get
  growth_diary_client.py patch --payload /tmp/patch.json
  growth_diary_client.py upload --session-id sess_0053 --file /tmp/photo.jpg
"""
from __future__ import annotations

import argparse, json, mimetypes, os, re, time, urllib.error, urllib.request
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
    return str(arg or os.getenv("XDY_RUNTIME_BASE_URL") or os.getenv("XIAODUIYOU_RUNTIME_BASE_URL") or os.getenv("XIAODUIYOU_BASE_URL") or os.getenv("XDY_BASE_URL") or config_extra().get("base_url") or "http://localhost:5173").rstrip("/")


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


def upload_asset(base: str, tok: str, file_path: Path, *, session_id: str | None = None, document_id: str | None = None) -> dict[str, Any]:
    boundary = f"----XDYGrowthDiary{int(time.time() * 1000)}"
    filename = file_path.name
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    fields = {"source": "growth_diary"}
    if session_id:
        fields["session_id"] = session_id
    if document_id:
        fields["document_id"] = document_id
    chunks: list[bytes] = []
    for k, v in fields.items():
        chunks += [f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()]
    chunks += [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
        file_path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    req = urllib.request.Request(
        f"{base}/api/assets",
        data=b"".join(chunks),
        method="POST",
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "X-XDY-Connector-Provider": "hermes",
            "X-XDY-Connector-Version": VERSION,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"asset upload HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc
    url = str(data.get("url") or ((data.get("asset") or {}).get("public_url")) or "")
    if url.startswith(("http://", "https://")):
        req2 = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req2, timeout=TIMEOUT) as resp:
            data["verified"] = {"http": resp.status, "content_type": resp.headers.get("content-type")}
    return data


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url")
    p.add_argument("--token")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("get")
    pp = sub.add_parser("patch")
    pp.add_argument("--payload", required=True, help="Path to JSON PATCH payload or raw JSON string")
    up = sub.add_parser("upload")
    up.add_argument("--file", required=True)
    up.add_argument("--session-id")
    up.add_argument("--document-id")
    args = p.parse_args()
    base, tok = base_url(args.base_url), token(args.token)
    if args.cmd == "get":
        print(json.dumps(request_json(f"{base}/api/growth-diary", tok=tok), ensure_ascii=False, indent=2))
    elif args.cmd == "patch":
        raw = Path(args.payload).read_text(encoding="utf-8") if Path(args.payload).exists() else args.payload
        payload = json.loads(raw)
        print(json.dumps(request_json(f"{base}/api/growth-diary", method="PATCH", tok=tok, payload=payload), ensure_ascii=False, indent=2))
    elif args.cmd == "upload":
        print(json.dumps(upload_asset(base, tok, Path(args.file).expanduser(), session_id=args.session_id, document_id=args.document_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
