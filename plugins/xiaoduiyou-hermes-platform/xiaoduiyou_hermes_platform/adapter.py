"""Xiaoduiyou Hermes platform adapter and document tools.

This plugin is intentionally a real Gateway platform + ToolRegistry integration:
Xiaoduiyou exposes pending-turn/callback APIs; Hermes owns the model loop; document
mutations happen only when the model calls xiaoduiyou document tools.
"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import tempfile
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, parse, request

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult
from gateway.session import SessionSource

logger = logging.getLogger(__name__)

TOOLSET = "xiaoduiyou"
XIAODUIYOU_HERMES_PLUGIN_VERSION = "2026.6.12.1"
DEFAULT_BASE_URL = "http://localhost:5173"
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 30.0
CHANNEL_DIRECTORY_REFRESH_SECONDS = 5.0

# Tool calls and adapter.send() run in the same gateway task context, so this
# lets tools enqueue structured document mutations that send() includes in the
# final Xiaoduiyou callback. The app then creates tool.call.completed events.
_PENDING_DOCUMENT_ACTIONS: ContextVar[List[Dict[str, Any]] | None] = ContextVar(
    "XIAODUIYOU_PENDING_DOCUMENT_ACTIONS",
    default=None,
)

# First-class Xiaoduiyou tools (Growth Diary, assets, etc.) must use the
# connector-owned origin/token for the active turn. The model should never have
# to inspect local env/config files or search for connection_token itself.
_ACTIVE_XIAODUIYOU_TOOL_CONTEXT: ContextVar[Dict[str, Any] | None] = ContextVar(
    "XIAODUIYOU_ACTIVE_TOOL_CONTEXT",
    default=None,
)

# Gateway delivery may call send() through the runner's adapter lookup rather than
# the exact object that claimed the turn, so keep a module-level fallback map in
# addition to per-adapter state. This is intentionally tiny and drained on send.
_TURN_BY_SESSION: Dict[str, str] = {}
_ACTIONS_BY_SESSION: Dict[str, List[Dict[str, Any]]] = {}
_PROGRESS_BY_MESSAGE: Dict[str, str] = {}
_PROGRESS_COUNTER = 0



def _sender_display_name_from_turn(turn: Dict[str, Any]) -> str:
    for key in ("sender_display_name", "sender_name", "display_name", "sender_email"):
        value = str(turn.get(key) or "").strip()
        if value:
            return value
    return "Xiaoduiyou user"


def _sender_id_from_turn(turn: Dict[str, Any]) -> str:
    for key in ("sender_account_id", "sender_id", "account_id"):
        value = str(turn.get(key) or "").strip()
        if value:
            return value
    return "xiaoduiyou-user"


def _hermes_user_id_from_turn(turn: Dict[str, Any]) -> str:
    # Hermes pairing belongs to the connected Xiaoduiyou home, while the actual
    # family member sender is preserved in the message text and runtime context.
    for key in ("account_id", "home_id"):
        value = str(turn.get(key) or "").strip()
        if value:
            return value
    runtime_context = turn.get("agent_runtime_context") or turn.get("runtime_context")
    if isinstance(runtime_context, dict):
        for key in ("account_id", "home_id", "family_id"):
            value = str(runtime_context.get(key) or "").strip()
            if value:
                return value
    return _sender_id_from_turn(turn)


def _chat_type_for_session(session: Dict[str, Any]) -> str:
    return "group" if str(session.get("session_scope") or "") == "family" else "dm"


def _is_stale_session_title(title: str) -> bool:
    stripped = title.strip()
    return stripped == "悬浮会话" or stripped.startswith("sess_")


def _channels_for_agent_sessions(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    channels: List[Dict[str, Any]] = [{
        "id": "default",
        "name": "主对话",
        "type": "dm",
    }]
    seen_ids = {"default"}
    hidden_purposes = {"growth_diary", "content_package", "feedback", "home_channel"}
    for session in sessions:
        session_id = str(session.get("session_id") or "").strip()
        if not session_id or session_id in seen_ids:
            continue
        if str(session.get("session_purpose") or "") in hidden_purposes:
            continue
        title = str(session.get("title") or session_id).strip() or session_id
        if _is_stale_session_title(title):
            continue
        channels.append({
            "id": session_id,
            "name": title,
            "type": _chat_type_for_session(session),
        })
        seen_ids.add(session_id)
    return channels


def _hermes_channel_directory_path() -> Path:
    try:
        from hermes_cli.config import get_hermes_home
        return get_hermes_home() / "channel_directory.json"
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "channel_directory.json"


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_xiaoduiyou_channel_directory(channels: List[Dict[str, Any]], path: Optional[Path] = None) -> None:
    directory_path = path or _hermes_channel_directory_path()
    directory: Dict[str, Any] = {"updated_at": None, "platforms": {}}
    if directory_path.exists():
        try:
            loaded = json.loads(directory_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                directory = loaded
        except Exception:
            directory = {"updated_at": None, "platforms": {}}

    platforms = directory.get("platforms")
    if not isinstance(platforms, dict):
        platforms = {}
    platforms["xiaoduiyou"] = [
        {
            "id": str(channel.get("id") or ""),
            "name": str(channel.get("name") or channel.get("id") or ""),
            "type": str(channel.get("type") or "dm"),
            **({"thread_id": str(channel.get("thread_id"))} if channel.get("thread_id") else {}),
        }
        for channel in channels
        if str(channel.get("id") or "").strip() and str(channel.get("name") or channel.get("id") or "").strip()
    ]
    directory["platforms"] = platforms
    directory["updated_at"] = datetime.now().isoformat()
    _atomic_write_json(directory_path, directory)


def _extract_xiaoduiyou_audio_attachments_from_turn(turn: Dict[str, Any]) -> List[Dict[str, Any]]:
    attachments: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add_attachment(url: str, mime_type: str = "", duration_ms: Any = None) -> None:
        clean_url = str(url or "").strip()
        if not clean_url.startswith(("http://", "https://")) or clean_url in seen:
            return
        seen.add(clean_url)
        attachment: Dict[str, Any] = {"url": clean_url}
        clean_mime_type = str(mime_type or "").strip()
        if clean_mime_type:
            attachment["mime_type"] = clean_mime_type
        if isinstance(duration_ms, (int, float)):
            attachment["duration_ms"] = int(duration_ms)
        attachments.append(attachment)

    add_attachment(
        str(turn.get("audio_url") or ""),
        str(turn.get("audio_mime_type") or ""),
        turn.get("audio_duration_ms"),
    )
    content_parts = turn.get("content_parts")
    if isinstance(content_parts, list):
        for part in content_parts:
            if not isinstance(part, dict) or part.get("type") != "audio_url":
                continue
            audio = part.get("audio_url") or {}
            url = str(audio.get("url") or "").strip() if isinstance(audio, dict) else ""
            add_attachment(url, str(part.get("mime_type") or ""), part.get("duration_ms"))
    return attachments


def _format_audio_attachments_for_agent(turn: Dict[str, Any]) -> str:
    attachments = _extract_xiaoduiyou_audio_attachments_from_turn(turn)
    if not attachments:
        return ""
    lines = ["语音附件："]
    for index, attachment in enumerate(attachments, start=1):
        details = []
        if attachment.get("mime_type"):
            details.append(f"mime_type={attachment['mime_type']}")
        if attachment.get("duration_ms") is not None:
            details.append(f"duration_ms={attachment['duration_ms']}")
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"{index}. {attachment['url']}{suffix}")
    return "\n".join(lines)


def _format_screen_context_for_agent(turn: Dict[str, Any]) -> str:
    screen_context = turn.get("screen_context")
    if not isinstance(screen_context, dict):
        return ""
    summary = str(screen_context.get("summary") or "").strip()
    if not summary:
        return ""
    lines = ["当前屏幕：", summary]
    details: List[str] = []
    for label, key in (("页面", "active_tab"), ("标题", "title"), ("内容包", "artifact_id"), ("文档", "document_id")):
        value = str(screen_context.get(key) or "").strip()
        if value:
            details.append(f"{label}：{value}")
    if details:
        lines.append("；".join(details))
    visible_text = str(screen_context.get("visible_text") or "").strip()
    if visible_text:
        lines.append(f"可见内容摘要：{visible_text}")
    return "\n".join(lines)


def _format_runtime_context_for_agent(turn: Dict[str, Any]) -> str:
    runtime_context = turn.get("agent_runtime_context") or turn.get("runtime_context")
    if not isinstance(runtime_context, dict):
        return ""
    base_url = str(runtime_context.get("base_url") or runtime_context.get("origin") or runtime_context.get("api_origin") or "").strip()
    if not base_url:
        return ""
    sender_raw = runtime_context.get("sender")
    auth_raw = runtime_context.get("auth")
    sender: Dict[str, Any] = sender_raw if isinstance(sender_raw, dict) else {}
    auth: Dict[str, Any] = auth_raw if isinstance(auth_raw, dict) else {}
    lines = [
        "小队友平台上下文：",
        "platform=xiaoduiyou",
        f"origin={base_url}",
    ]
    for label, key in (
        ("environment", "environment"),
        ("home_id", "home_id"),
        ("family_id", "family_id"),
        ("session_id", "session_id"),
        ("session_scope", "session_scope"),
        ("session_purpose", "session_purpose"),
        ("surface", "surface"),
    ):
        value = str(runtime_context.get(key) or "").strip()
        if value:
            lines.append(f"{label}={value}")
    sender_bits = []
    for key in ("display_name", "account_id", "role"):
        value = str(sender.get(key) or "").strip()
        if value:
            sender_bits.append(f"{key}={value}")
    if sender_bits:
        lines.append(f"sender: {', '.join(sender_bits)}")
    provider = str(auth.get("provider") or "").strip()
    if provider:
        lines.append(f"auth.provider={provider}; auth.mode=connection_token_bound")
    lines.append("本次 Xiaoduiyou API/成长日记/资产/频道写入必须使用上述 origin 与当前连接 token；禁止改用本地 config、生产/测试默认地址、维护者 URL 或浏览器里打开的其他小队友页面。")
    return "\n".join(lines)


def _agent_event_text_for_turn(turn_or_message: Any) -> str:
    if not isinstance(turn_or_message, dict):
        return str(turn_or_message or "").strip()
    user_message = str(turn_or_message.get("user_message") or turn_or_message.get("content") or "").strip()
    sender_name = _sender_display_name_from_turn(turn_or_message)
    sender_id = _sender_id_from_turn(turn_or_message)
    audio_note = _format_audio_attachments_for_agent(turn_or_message)
    screen_note = _format_screen_context_for_agent(turn_or_message)
    runtime_note = _format_runtime_context_for_agent(turn_or_message)
    agent_notice = str(turn_or_message.get("agent_notice") or "").strip()
    parts = [f"发送者：{sender_name}（{sender_id}）", screen_note, runtime_note, agent_notice, user_message]
    if audio_note:
        parts.append(audio_note)
    return "\n\n".join(part for part in parts if part).strip()


def _extract_xiaoduiyou_image_urls(text: str) -> List[str]:
    image_urls: List[str] = []
    for block in str(text or "").split("图片：")[1:]:
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if not line[0].isdigit():
                break
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue
            url = parts[1].strip()
            if url.startswith("http://") or url.startswith("https://"):
                image_urls.append(url)
    return image_urls


def _extract_xiaoduiyou_image_urls_from_turn(turn: Dict[str, Any]) -> List[str]:
    image_urls = turn.get("image_urls")
    if isinstance(image_urls, list):
        urls = [str(url).strip() for url in image_urls if str(url).strip().startswith(("http://", "https://"))]
        if urls:
            return urls
    content_parts = turn.get("content_parts")
    if isinstance(content_parts, list):
        urls: List[str] = []
        for part in content_parts:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            image = part.get("image_url") or {}
            url = str(image.get("url") or "").strip() if isinstance(image, dict) else ""
            if url.startswith(("http://", "https://")):
                urls.append(url)
        if urls:
            return urls
    return _extract_xiaoduiyou_image_urls(str(turn.get("user_message") or ""))


def _download_image_attachments(image_urls: List[str], timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Tuple[List[str], List[str]]:
    media_paths: List[str] = []
    media_types: List[str] = []
    for index, url in enumerate(image_urls):
        try:
            req = request.Request(url, method="GET", headers={"user-agent": "Xiaoduiyou-Hermes/1.0"})
            with request.urlopen(req, timeout=timeout) as resp:
                content_type = str(resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                if not content_type.startswith("image/"):
                    logger.warning("Xiaoduiyou image attachment skipped non-image URL %s content_type=%s", url, content_type)
                    continue
                data = resp.read()
            suffix = mimetypes.guess_extension(content_type) or f".{content_type.split('/')[-1] or 'img'}"
            fd, path = tempfile.mkstemp(prefix=f"xiaoduiyou-image-{index + 1}-", suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            media_paths.append(path)
            media_types.append(content_type)
        except Exception as exc:
            logger.warning("Xiaoduiyou image attachment download failed for %s: %s", url, exc)
    return media_paths, media_types

def _active_actions() -> List[Dict[str, Any]]:
    actions = _PENDING_DOCUMENT_ACTIONS.get()
    if actions is None:
        actions = []
        _PENDING_DOCUMENT_ACTIONS.set(actions)
    return actions


def _queue_action(action: Dict[str, Any]) -> None:
    _active_actions().append(action)
    chat_id = _get_session_chat_id()
    if chat_id:
        _ACTIONS_BY_SESSION.setdefault(chat_id, []).append(action)


def _drain_actions(chat_id: str = "") -> List[Dict[str, Any]]:
    actions = list(_PENDING_DOCUMENT_ACTIONS.get() or [])
    _PENDING_DOCUMENT_ACTIONS.set([])
    if chat_id:
        session_actions = _ACTIONS_BY_SESSION.pop(str(chat_id), [])
        if session_actions and not actions:
            actions = session_actions
        elif session_actions:
            seen = {json.dumps(action, sort_keys=True, ensure_ascii=False) for action in actions}
            actions.extend(
                action for action in session_actions
                if json.dumps(action, sort_keys=True, ensure_ascii=False) not in seen
            )
    return actions


def _block(text: str, block_type: str = "paragraph") -> Dict[str, Any]:
    return {"type": block_type, "content": [{"type": "text", "text": text, "styles": {}}]}


def _block_json_from_text(title: str = "", body: str = "") -> Dict[str, Any]:
    blocks: List[Dict[str, Any]] = []
    if title:
        blocks.append(_block(title, "heading"))
    for raw in (body or "").splitlines():
        line = raw.strip()
        if line:
            blocks.append(_block(line))
    return {"schema": "xdy.block_json.v1", "blocks": blocks}


def _normalize_block_json(value: Any, *, title: str = "", body: str = "") -> Dict[str, Any]:
    if isinstance(value, dict) and value.get("schema") == "xdy.block_json.v1" and isinstance(value.get("blocks"), list):
        return value
    return _block_json_from_text(title=title, body=body)


def _normalize_ui_templates(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    allowed = {"xiaohongshu", "moments"}
    templates: List[str] = []
    for item in value:
        key = str(item or "").strip()
        if key in allowed and key not in templates:
            templates.append(key)
    return templates


def _merge_ui_templates_into_fields(args: Dict[str, Any], fields: Any) -> Dict[str, Any]:
    normalized_fields: Dict[str, Any] = dict(fields) if isinstance(fields, dict) else {}
    templates = _normalize_ui_templates(args.get("ui_templates"))
    if templates:
        normalized_fields["ui_templates"] = templates
    return normalized_fields


def _json_response(req: request.Request, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw or "{}")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def _connection_token_from_config(config: PlatformConfig | None = None) -> str:
    if os.getenv("XIAODUIYOU_CONNECTION_TOKEN"):
        return os.getenv("XIAODUIYOU_CONNECTION_TOKEN", "").strip()
    extra = getattr(config, "extra", None) or {}
    if isinstance(extra, dict) and extra.get("connection_token"):
        return str(extra["connection_token"]).strip()
    try:
        import yaml
        from hermes_constants import get_hermes_home
        cfg_path = os.path.join(get_hermes_home(), "config.yaml")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        extra = (((cfg.get("platforms") or {}).get("xiaoduiyou") or {}).get("extra") or {})
        if extra.get("connection_token"):
            return str(extra["connection_token"]).strip()
    except Exception:
        pass
    return ""


def _request_json(url: str, *, method: str = "GET", payload: Optional[Dict[str, Any]] = None, timeout: float = DEFAULT_TIMEOUT_SECONDS, token: str = "") -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "X-XDY-Connector-Version": XIAODUIYOU_HERMES_PLUGIN_VERSION,
        "X-XDY-Connector-Provider": "hermes",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = request.Request(
        url,
        method=method,
        data=data,
        headers=headers,
    )
    return _json_response(req, timeout=timeout)



def _upload_asset_file(base_url: str, token: str, path: str, *, session_id: str = "", turn_id: str = "", document_id: str = "", timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    boundary = f"----XiaoduiyouHermes{int(time.time() * 1000)}"
    filename = os.path.basename(path) or "image"
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    fields = {"source": "external_import", "require_remote_storage": "true"}
    if session_id:
        fields["session_id"] = session_id
    if turn_id:
        fields["turn_id"] = turn_id
    if document_id:
        fields["document_id"] = document_id
    chunks: List[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
    chunks.append(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
    with open(path, "rb") as f:
        chunks.append(f.read())
    chunks.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    headers = {
        "content-type": f"multipart/form-data; boundary={boundary}",
        "X-XDY-Connector-Version": XIAODUIYOU_HERMES_PLUGIN_VERSION,
        "X-XDY-Connector-Provider": "hermes",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = request.Request(
        f"{base_url}/api/assets",
        method="POST",
        data=b"".join(chunks),
        headers=headers,
    )
    result = _json_response(req, timeout=timeout)
    url = str(result.get("url") or ((result.get("asset") or {}).get("public_url")) or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("Xiaoduiyou asset upload did not return a public URL")
    return url


def _assetize_visual_card_payload(base_url: str, token: str, session_id: str, payload: Dict[str, Any], timeout: float = DEFAULT_TIMEOUT_SECONDS, *, turn_id: str = "", document_id: str = "") -> Dict[str, Any]:
    if not token:
        return payload
    next_payload = dict(payload)
    raw_attachments = next_payload.get("image_attachments")
    if isinstance(raw_attachments, list):
        next_attachments: List[Dict[str, Any]] = []
        for item in raw_attachments:
            if not isinstance(item, dict):
                continue
            attachment = dict(item)
            image_url = str(attachment.get("image_url") or attachment.get("url") or "").strip()
            if image_url.startswith(("http://", "https://")) and not image_url.startswith(base_url):
                try:
                    media_paths, _media_types = _download_image_attachments([image_url], timeout)
                    if media_paths:
                        try:
                            attachment["image_url"] = _upload_asset_file(base_url, token, media_paths[0], session_id=session_id, turn_id=turn_id, document_id=document_id, timeout=timeout)
                        finally:
                            try:
                                os.unlink(media_paths[0])
                            except OSError:
                                pass
                except Exception as exc:
                    logger.warning("Xiaoduiyou visual card image asset upload failed for %s: %s", image_url, exc)
            next_attachments.append(attachment)
        next_payload["image_attachments"] = next_attachments
        if "image_urls" not in next_payload:
            next_payload["image_urls"] = [str(item.get("image_url") or "") for item in next_attachments if isinstance(item, dict) and str(item.get("image_url") or "").startswith(("http://", "https://"))]
    return next_payload

def _get_session_chat_id() -> str:
    try:
        from gateway.session_context import get_session_env
        return get_session_env("HERMES_SESSION_CHAT_ID", "") or ""
    except Exception:
        return os.getenv("HERMES_SESSION_CHAT_ID", "") or ""


def _base_url_from_config(config: PlatformConfig | None = None) -> str:
    if os.getenv("XIAODUIYOU_BASE_URL"):
        return os.getenv("XIAODUIYOU_BASE_URL", "").rstrip("/")
    extra = getattr(config, "extra", None) or {}
    if isinstance(extra, dict) and extra.get("base_url"):
        return str(extra["base_url"]).rstrip("/")
    try:
        import yaml
        from hermes_constants import get_hermes_home
        cfg_path = os.path.join(get_hermes_home(), "config.yaml")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        extra = (((cfg.get("platforms") or {}).get("xiaoduiyou") or {}).get("extra") or {})
        if extra.get("base_url"):
            return str(extra["base_url"]).rstrip("/")
    except Exception:
        pass
    return DEFAULT_BASE_URL


def check_requirements() -> bool:
    # No external dependency; network availability is checked lazily.
    return True


def validate_config(config: PlatformConfig) -> tuple[bool, str]:
    base_url = _base_url_from_config(config)
    return (bool(base_url), "" if base_url else "Xiaoduiyou base_url is missing")


def is_connected() -> bool:
    base_url = _base_url_from_config()
    try:
        _request_json(f"{base_url}/api/version", timeout=5)
        return True
    except Exception:
        return False


class XiaoduiyouAdapter(BasePlatformAdapter):
    MAX_MESSAGE_LENGTH = 12000

    def __init__(self, config: PlatformConfig):
        super().__init__(config=config, platform=Platform("xiaoduiyou"))
        extra = getattr(config, "extra", {}) or {}
        self.base_url = _base_url_from_config(config)
        self.poll_interval_seconds = float(extra.get("poll_interval_seconds") or DEFAULT_POLL_INTERVAL_SECONDS)
        self.request_timeout_seconds = float(extra.get("request_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
        self.connection_token = _connection_token_from_config(config)
        self._poll_task: asyncio.Task | None = None
        self._turn_by_session: Dict[str, str] = {}
        self._last_claim_at = 0.0
        self._last_channel_directory_refresh_at = 0.0

    @property
    def name(self) -> str:
        return "Xiaoduiyou"

    async def connect(self) -> bool:
        if not self.base_url:
            self._set_fatal_error("config_missing", "Xiaoduiyou base_url is missing", retryable=False)
            return False
        self._running = True
        self._mark_connected()
        self._poll_task = asyncio.create_task(self._poll_loop())
        if not self.connection_token:
            logger.warning("Xiaoduiyou connection_token is missing; authenticated polling endpoints may return 401")
        logger.info("Xiaoduiyou: connected to %s", self.base_url)
        return True

    async def disconnect(self) -> None:
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._mark_disconnected()

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"name": f"Xiaoduiyou {chat_id}", "type": "dm"}

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._refresh_channel_directory_if_due()
                claimed = await asyncio.to_thread(self._claim_pending_turn)
                if claimed:
                    await self._handle_claimed_turn(claimed)
                else:
                    await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Xiaoduiyou poll failed: %s", exc)
                await asyncio.sleep(max(self.poll_interval_seconds, 3.0))

    def _claim_pending_turn(self) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/hermes/turns/pending"
        try:
            result = _request_json(url, timeout=self.request_timeout_seconds, token=self.connection_token)
            self._last_claim_at = time.time()
            return result
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    async def _handle_claimed_turn(self, claimed: Dict[str, Any]) -> None:
        turn = claimed.get("turn") or {}
        session = claimed.get("session") or {}
        turn_id = str(turn.get("turn_id") or "")
        session_id = str(turn.get("session_id") or session.get("session_id") or "")
        user_message = str(turn.get("user_message") or "").strip()
        agent_message = _agent_event_text_for_turn(turn)
        sender_name = _sender_display_name_from_turn(turn)
        sender_id = _sender_id_from_turn(turn)
        hermes_user_id = _hermes_user_id_from_turn(turn)
        if not turn_id or not session_id or not user_message:
            logger.warning("Xiaoduiyou claimed malformed turn: %s", claimed)
            return

        if str(turn.get("input_type") or "") == "command":
            self._turn_by_session[session_id] = turn_id
            _TURN_BY_SESSION[session_id] = turn_id
            _PENDING_DOCUMENT_ACTIONS.set([])
            _ACTIVE_XIAODUIYOU_TOOL_CONTEXT.set(self._tool_context_for_turn(turn, session_id=session_id, turn_id=turn_id))
            _ACTIONS_BY_SESSION.pop(session_id, None)
            command_text = str(turn.get("command_name") or user_message).strip() or user_message
            if not command_text.startswith("/"):
                command_text = f"/{command_text}"
            source = SessionSource(
                platform=Platform("xiaoduiyou"),
                chat_id=session_id,
                chat_name=str(session.get("title") or "Xiaoduiyou"),
                chat_type=_chat_type_for_session(session),
                user_id=hermes_user_id,
                user_name=sender_name,
                message_id=turn_id,
            )
            event = MessageEvent(
                text=command_text,
                message_type=MessageType.COMMAND,
                source=source,
                raw_message=dict(claimed),
                message_id=turn_id,
            )
            await self.handle_message(event)
            return

        self._turn_by_session[session_id] = turn_id
        _TURN_BY_SESSION[session_id] = turn_id
        _PENDING_DOCUMENT_ACTIONS.set([])
        _ACTIVE_XIAODUIYOU_TOOL_CONTEXT.set(self._tool_context_for_turn(turn, session_id=session_id, turn_id=turn_id))
        _ACTIONS_BY_SESSION.pop(session_id, None)

        document_tool_note = (
            "Xiaoduiyou connector tools are available. "
            "For Growth Diary tasks, use skill xiaoduiyou-growth-diary, call xiaoduiyou_growth_diary_get first, then xiaoduiyou_growth_diary_patch for writes; "
            "do not search local files/env/config for connection_token and do not call /api/growth-diary manually from terminal. "
            "For Growth Diary event time, use explicit user wording first; if absent, use this Xiaoduiyou turn's created_at, never the Agent runtime clock or an invented time. "
            "Agent-created records must include date as YYYY-MM-DD and occurred_at as YYYY-MM-DD HH:mm:ss with matching dates; short times like 19:20 are invalid and will be rejected. "
            "For ordinary chat, answer normally and do not call document tools. "
            "When the user explicitly asks to create, update, append to, or delete a document, "
            "call the appropriate xiaoduiyou document tool exactly once before your final reply. "
            "For content packages, choose UI templates with ui_templates (currently xiaohongshu and/or moments) "
            "and fill matching fields.publish_notes.<template> with final result data; process block_json/source_markdown should stay process-only. "
            "Do not merely promise to create a document."
        )
        image_urls = _extract_xiaoduiyou_image_urls_from_turn(turn)
        media_paths, media_types = await asyncio.to_thread(
            _download_image_attachments,
            image_urls,
            self.request_timeout_seconds,
        ) if image_urls else ([], [])

        raw = dict(claimed)
        raw["xiaoduiyou_document_tool_note"] = document_tool_note
        raw["xiaoduiyou_image_urls"] = image_urls
        raw["xiaoduiyou_downloaded_image_paths"] = media_paths
        source = SessionSource(
            platform=Platform("xiaoduiyou"),
            chat_id=session_id,
            chat_name=str(session.get("title") or "Xiaoduiyou"),
            chat_type=_chat_type_for_session(session),
            user_id=hermes_user_id,
            user_name=sender_name,
            message_id=turn_id,
        )
        event = MessageEvent(
            text=agent_message,
            message_type=MessageType.PHOTO if media_paths else MessageType.TEXT,
            source=source,
            raw_message=raw,
            message_id=turn_id,
            media_urls=media_paths,
            media_types=media_types,
            channel_prompt=document_tool_note,
        )
        await self.handle_message(event)

    def _tool_context_for_turn(self, turn: Dict[str, Any], *, session_id: str = "", turn_id: str = "") -> Dict[str, Any]:
        runtime_context = turn.get("agent_runtime_context") or turn.get("runtime_context")
        runtime_context = runtime_context if isinstance(runtime_context, dict) else {}
        screen_context = turn.get("screen_context") or {}
        screen_context = screen_context if isinstance(screen_context, dict) else {}
        base_url = str(
            runtime_context.get("api_origin")
            or runtime_context.get("base_url")
            or runtime_context.get("origin")
            or self.base_url
            or ""
        ).rstrip("/")
        return {
            "base_url": base_url,
            "token": self.connection_token,
            "session_id": session_id or str(runtime_context.get("session_id") or ""),
            "turn_id": turn_id,
            "document_id": str(screen_context.get("document_id") or runtime_context.get("document_id") or ""),
            "home_id": str(runtime_context.get("home_id") or ""),
            "family_id": str(runtime_context.get("family_id") or ""),
            "environment": str(runtime_context.get("environment") or ""),
        }

    async def _post_turn_event(self, turn_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await asyncio.to_thread(
            _request_json,
            f"{self.base_url}/api/hermes/turns/{turn_id}/events",
            method="POST",
            payload=payload,
            timeout=self.request_timeout_seconds,
            token=self.connection_token,
        )

    def _session_message_payload_from_content(self, content: str) -> Dict[str, Any]:
        raw = str(content or "").strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and any(key in parsed for key in ("message_type", "tool_progress", "image_attachments", "image_urls", "text", "content", "detail")):
                    return parsed
            except Exception:
                pass
        return {"text": raw}

    def _list_agent_sessions(self) -> List[Dict[str, Any]]:
        result = _request_json(
            f"{self.base_url}/api/agent/sessions",
            timeout=self.request_timeout_seconds,
            token=self.connection_token,
        )
        sessions = result.get("sessions")
        return [session for session in sessions if isinstance(session, dict)] if isinstance(sessions, list) else []

    async def list_channels(self) -> List[Dict[str, Any]]:
        try:
            sessions = await asyncio.to_thread(self._list_agent_sessions)
        except Exception as exc:
            logger.warning("Xiaoduiyou session list lookup failed for channel directory: %s", exc)
            return _channels_for_agent_sessions([])
        return _channels_for_agent_sessions(sessions)

    async def _refresh_channel_directory_if_due(self) -> None:
        now = time.time()
        if now - self._last_channel_directory_refresh_at < CHANNEL_DIRECTORY_REFRESH_SECONDS:
            return
        self._last_channel_directory_refresh_at = now
        try:
            channels = await self.list_channels()
            await asyncio.to_thread(_write_xiaoduiyou_channel_directory, channels)
        except Exception as exc:
            logger.debug("Xiaoduiyou channel directory compatibility refresh failed: %s", exc)

    def _resolve_session_id_for_outbound(self, chat_id: str) -> str:
        chat_key = str(chat_id or "").strip()
        try:
            sessions = self._list_agent_sessions()
        except Exception as exc:
            logger.warning("Xiaoduiyou session list lookup failed for outbound target %s: %s", chat_key, exc)
            return chat_key
        if not sessions:
            return chat_key

        for session in sessions:
            if str(session.get("session_id") or "") == chat_key:
                return chat_key
        for session in sessions:
            if str(session.get("title") or "").strip() == chat_key:
                return str(session.get("session_id") or chat_key)

        alias_targets = {"", "xiaoduiyou", "home", "default", "主对话"}
        if chat_key in alias_targets:
            for session in sessions:
                if str(session.get("session_purpose") or "") == "home_channel":
                    return str(session.get("session_id") or chat_key)
            return str(sessions[0].get("session_id") or chat_key)
        return chat_key

    def _is_home_channel_alias(self, chat_id: str) -> bool:
        return str(chat_id or "").strip() in {"", "xiaoduiyou", "home", "default", "主对话"}

    async def _post_session_message(self, chat_id: str, content: str) -> Dict[str, Any]:
        content = _clean_xiaoduiyou_delivery_content(content)
        if self._is_home_channel_alias(chat_id):
            payload = self._session_message_payload_from_content(content)
            im_payload: Dict[str, Any] = {"channel": "default"}
            if str(payload.get("message_type") or "") == "tool_progress" or payload.get("tool_progress"):
                im_payload["message_type"] = "tool_progress"
                im_payload["tool_progress"] = str(payload.get("tool_progress") or payload.get("text") or payload.get("content") or payload.get("detail") or "")
            else:
                im_payload["text"] = str(payload.get("text") or payload.get("content") or payload.get("detail") or content or "")
            return await asyncio.to_thread(
                _request_json,
                f"{self.base_url}/api/agent/im/send",
                method="POST",
                payload=im_payload,
                timeout=self.request_timeout_seconds,
                token=self.connection_token,
            )

        session_id = await asyncio.to_thread(self._resolve_session_id_for_outbound, chat_id)
        payload = self._session_message_payload_from_content(content)
        payload = await asyncio.to_thread(
            _assetize_visual_card_payload,
            self.base_url,
            self.connection_token,
            session_id,
            payload,
            self.request_timeout_seconds,
        )
        return await asyncio.to_thread(
            _request_json,
            f"{self.base_url}/api/agent/sessions/{session_id}/messages",
            method="POST",
            payload=payload,
            timeout=self.request_timeout_seconds,
            token=self.connection_token,
        )

    async def _post_interactive_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await asyncio.to_thread(
            _request_json,
            f"{self.base_url}/api/hermes/interactive-requests",
            method="POST",
            payload=payload,
            timeout=self.request_timeout_seconds,
            token=self.connection_token,
        )

    async def _get_interactive_request(self, request_id: str) -> Dict[str, Any]:
        return await asyncio.to_thread(
            _request_json,
            f"{self.base_url}/api/hermes/interactive-requests/{request_id}",
            timeout=self.request_timeout_seconds,
            token=self.connection_token,
        )

    def _watch_exec_approval(self, request_id: str, session_key: str, timeout_seconds: int = 300) -> None:
        async def _run() -> None:
            deadline = time.time() + timeout_seconds
            while self._running and time.time() < deadline:
                await asyncio.sleep(1)
                try:
                    result = await self._get_interactive_request(request_id)
                    interactive_request = result.get("request") if isinstance(result, dict) else {}
                    if not isinstance(interactive_request, dict):
                        continue
                    status = str(interactive_request.get("status") or "")
                    if status == "resolved":
                        choice = str(interactive_request.get("choice") or "")
                        if choice:
                            try:
                                from tools.approval import resolve_gateway_approval
                                resolve_gateway_approval(session_key, choice)
                            except Exception as exc:
                                logger.error("Xiaoduiyou exec approval resolve failed: %s", exc, exc_info=True)
                        return
                    if status == "expired":
                        return
                except Exception as exc:
                    logger.debug("Xiaoduiyou exec approval poll failed for %s: %s", request_id, exc)

        asyncio.create_task(_run())

    def _watch_slash_confirm(self, request_id: str, session_key: str, confirm_id: str, chat_id: str, timeout_seconds: int = 300) -> None:
        async def _run() -> None:
            deadline = time.time() + timeout_seconds
            while self._running and time.time() < deadline:
                await asyncio.sleep(1)
                try:
                    result = await self._get_interactive_request(request_id)
                    interactive_request = result.get("request") if isinstance(result, dict) else {}
                    if not isinstance(interactive_request, dict):
                        continue
                    status = str(interactive_request.get("status") or "")
                    if status == "resolved":
                        choice = str(interactive_request.get("choice") or "")
                        if choice:
                            try:
                                from tools import slash_confirm as _slash_confirm_mod
                                followup = await _slash_confirm_mod.resolve(session_key, confirm_id, choice)
                                if followup:
                                    await self.send(chat_id, followup)
                            except Exception as exc:
                                logger.error("Xiaoduiyou slash confirm resolve failed: %s", exc, exc_info=True)
                        return
                    if status == "expired":
                        return
                except Exception as exc:
                    logger.debug("Xiaoduiyou slash confirm poll failed for %s: %s", request_id, exc)

        asyncio.create_task(_run())

    async def _resolve_turn_id(self, chat_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        chat_key = str(chat_id)
        turn_id = str((metadata or {}).get("turn_id") or self._turn_by_session.get(chat_key) or _TURN_BY_SESSION.get(chat_key) or "")
        if turn_id:
            return turn_id
        try:
            result = await asyncio.to_thread(
                _request_json,
                f"{self.base_url}/api/hermes/sessions/{chat_key}/turns/active",
                timeout=self.request_timeout_seconds,
                token=self.connection_token,
            )
            active_turn = result.get("turn") or {}
            turn_id = str(active_turn.get("turn_id") or "")
            if turn_id:
                self._turn_by_session[chat_key] = turn_id
                _TURN_BY_SESSION[chat_key] = turn_id
                return turn_id
        except Exception as exc:
            logger.warning("Xiaoduiyou active turn lookup failed for %s: %s", chat_key, exc)
        return ""

    async def send_exec_approval(
        self,
        chat_id: str,
        command: str,
        session_key: str,
        description: str = "dangerous command",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        session_id = str(chat_id or "").strip()
        turn_id = await self._resolve_turn_id(session_id, metadata)
        payload = {
            "session_id": session_id,
            "turn_id": turn_id,
            "kind": "exec_approval",
            "title": "需要授权执行命令",
            "message": description or "Agent 请求执行一条需要确认的命令。",
            "command": command or "",
            "reason": description or "",
            "session_key": session_key,
            "actions": ["once", "session", "always", "deny"],
            "timeout_seconds": 300,
        }
        try:
            result = await self._post_interactive_request(payload)
            interactive_request = result.get("request") if isinstance(result, dict) else {}
            request_id = str(interactive_request.get("request_id") or "") if isinstance(interactive_request, dict) else ""
            if request_id:
                self._watch_exec_approval(request_id, session_key)
            return SendResult(success=True, message_id=request_id or f"xiaoduiyou_approval_{int(time.time() * 1000)}", raw_response=result)
        except Exception as exc:
            logger.error("Xiaoduiyou exec approval request failed: %s", exc, exc_info=True)
            return SendResult(success=False, error=str(exc))

    async def send_slash_confirm(
        self,
        chat_id: str,
        title: str,
        message: str,
        session_key: str,
        confirm_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        session_id = str(chat_id or "").strip()
        turn_id = await self._resolve_turn_id(session_id, metadata)
        payload = {
            "session_id": session_id,
            "turn_id": turn_id,
            "kind": "slash_confirm",
            "title": title or "需要确认 Agent 指令",
            "message": message or "确认后 Agent 会继续执行。",
            "command": title or "",
            "confirm_id": confirm_id,
            "session_key": session_key,
            "actions": ["once", "always", "cancel"],
            "timeout_seconds": 300,
        }
        try:
            result = await self._post_interactive_request(payload)
            interactive_request = result.get("request") if isinstance(result, dict) else {}
            request_id = str(interactive_request.get("request_id") or "") if isinstance(interactive_request, dict) else ""
            if request_id:
                self._watch_slash_confirm(request_id, session_key, confirm_id, session_id)
            return SendResult(success=True, message_id=request_id or f"xiaoduiyou_confirm_{int(time.time() * 1000)}", raw_response=result)
        except Exception as exc:
            logger.error("Xiaoduiyou slash confirm request failed: %s", exc, exc_info=True)
            return SendResult(success=False, error=str(exc))

    async def send(self, chat_id: str, content: str, reply_to: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> SendResult:
        chat_key = str(chat_id)
        content = _clean_xiaoduiyou_delivery_content(content)
        turn_id = await self._resolve_turn_id(chat_key, metadata)
        if not turn_id:
            if "▉" in (content or ""):
                return SendResult(success=False, error="Xiaoduiyou does not stream assistant text; final reply is delivered through callback")
            try:
                fallback_content = content or ""
                if _looks_like_tool_progress(fallback_content):
                    result = await self._post_session_message(
                        chat_key,
                        json.dumps({"message_type": "tool_progress", "tool_progress": fallback_content}, ensure_ascii=False),
                    )
                else:
                    result = await self._post_session_message(chat_key, fallback_content)
                return SendResult(success=True, message_id=str(result.get("message_id") or f"xiaoduiyou:{int(time.time() * 1000)}"), raw_response=result)
            except Exception as exc:
                logger.error("Xiaoduiyou session message failed: %s", exc, exc_info=True)
                return SendResult(success=False, error=str(exc))

        if _looks_like_tool_progress(content):
            message_id = _next_progress_message_id(chat_key, "tool")
            _PROGRESS_BY_MESSAGE[message_id] = content or ""
            try:
                result = await self._post_turn_event(turn_id, {"tool_progress": content or ""})
                return SendResult(success=True, message_id=message_id, raw_response=result)
            except Exception as exc:
                logger.error("Xiaoduiyou progress event failed: %s", exc, exc_info=True)
                return SendResult(success=False, error=str(exc))

        if _looks_like_status_progress(content):
            message_id = _next_progress_message_id(chat_key, "status")
            try:
                result = await self._post_turn_event(turn_id, {"progress": content or ""})
                return SendResult(success=True, message_id=message_id, raw_response=result)
            except Exception as exc:
                logger.error("Xiaoduiyou status progress event failed: %s", exc, exc_info=True)
                return SendResult(success=False, error=str(exc))

        if "▉" in (content or ""):
            return SendResult(success=False, error="Xiaoduiyou does not stream assistant text; final reply is delivered through callback")

        actions = _drain_actions(chat_key)
        payload: Dict[str, Any] = {"progress": content or "完成。"}
        if actions:
            payload["document_actions"] = actions
        try:
            result = await asyncio.to_thread(
                _request_json,
                f"{self.base_url}/api/hermes/turns/{turn_id}/callback",
                method="POST",
                payload=payload,
                timeout=self.request_timeout_seconds,
                token=self.connection_token,
            )
            self._turn_by_session.pop(chat_key, None)
            _TURN_BY_SESSION.pop(chat_key, None)
            return SendResult(success=True, message_id=turn_id, raw_response=result)
        except Exception as exc:
            logger.error("Xiaoduiyou callback failed: %s", exc, exc_info=True)
            return SendResult(success=False, error=str(exc))

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        content: str,
        *,
        finalize: bool = False,
    ) -> SendResult:
        chat_key = str(chat_id)
        turn_id = await self._resolve_turn_id(chat_key)
        if not turn_id:
            return SendResult(success=False, error=f"No Xiaoduiyou pending turn for session {chat_id}")

        if str(message_id).startswith("xiaoduiyou_tool_") or _looks_like_tool_progress(content):
            delta = _progress_delta(str(message_id), content or "")
            if not delta:
                return SendResult(success=True, message_id=message_id)
            try:
                result = await self._post_turn_event(turn_id, {"tool_progress": delta})
                return SendResult(success=True, message_id=message_id, raw_response=result)
            except Exception as exc:
                logger.error("Xiaoduiyou progress edit failed: %s", exc, exc_info=True)
                return SendResult(success=False, error=str(exc))

        clean_content = (content or "").replace("▉", "").rstrip()
        if finalize:
            actions = _drain_actions(chat_key)
            payload: Dict[str, Any] = {"progress": clean_content or "完成。"}
            if actions:
                payload["document_actions"] = actions
            try:
                result = await asyncio.to_thread(
                    _request_json,
                    f"{self.base_url}/api/hermes/turns/{turn_id}/callback",
                    method="POST",
                    payload=payload,
                    timeout=self.request_timeout_seconds,
                    token=self.connection_token,
                )
                self._turn_by_session.pop(chat_key, None)
                _TURN_BY_SESSION.pop(chat_key, None)
                return SendResult(success=True, message_id=message_id, raw_response=result)
            except Exception as exc:
                logger.error("Xiaoduiyou final stream callback failed: %s", exc, exc_info=True)
                return SendResult(success=False, error=str(exc))

        return SendResult(success=False, error="Xiaoduiyou ignores intermediate assistant text streaming; final reply is delivered through callback")


def _queued_result(operation: str, action: Dict[str, Any]) -> str:
    payload: Dict[str, Any] = {
        "ok": True,
        "queued": True,
        "operation": operation,
        "will_apply_on": "final_callback",
        "next_step": "Continue the answer normally. Do not repeat this tool call just to verify; use xiaoduiyou_documents_get after the final callback or in a later turn.",
    }
    if action.get("document_id"):
        payload["document_id"] = action.get("document_id")
    else:
        payload["current_session_document"] = True
    if operation == "create":
        payload["attach_to_session"] = bool(action.get("attach_to_session", True))
    return json.dumps(payload, ensure_ascii=False)


def _next_progress_message_id(chat_id: str, kind: str = "progress") -> str:
    global _PROGRESS_COUNTER
    _PROGRESS_COUNTER += 1
    return f"xiaoduiyou_{kind}_{chat_id}_{_PROGRESS_COUNTER}"


def _looks_like_status_progress(content: str) -> bool:
    stripped = (content or "").strip()
    return stripped.startswith((
        "⏳ Still working...",
        "⚠️ No activity for ",
        "ℹ Codex ",
    ))


def _clean_xiaoduiyou_delivery_content(content: str) -> str:
    text = str(content or "")
    stripped = text.strip()
    if not stripped.startswith("Cronjob Response:"):
        return text

    body_lines: List[str] = []
    for index, line in enumerate(stripped.splitlines()):
        if index == 0:
            continue
        if index == 1 and line.strip().startswith("(job_id:"):
            continue
        if line.strip().startswith("To stop or manage this job"):
            break
        body_lines.append(line)
    body = "\n".join(body_lines).strip()
    return body or stripped


def _looks_like_tool_progress(content: str) -> bool:
    stripped = (content or "").strip()
    if not stripped:
        return False
    tool_markers = (
        "📨 send_message",
        "send_message(",
        "send_message:",
        "Tool\n",
        "Tool\r\n",
    )
    if any(marker in stripped for marker in tool_markers):
        return True
    return any(marker in stripped for marker in (': "', '...', '(', '×')) and any(
        stripped.startswith(prefix) for prefix in (
            '🔍', '🔎', '📖', '📚', '🛠', '⚙', '✅', '💻', '🌐', '📝', '📁', '🔧',
            '📋', '🐍', '🎨', '👁', '🧠', '⏰', '🍼', '📄', '✏️', '🗑️', '🖼️',
            '📨',
        )
    )


def _progress_delta(message_id: str, content: str) -> str:
    previous = _PROGRESS_BY_MESSAGE.get(message_id, "")
    current = content or ""
    _PROGRESS_BY_MESSAGE[message_id] = current
    if previous and current.startswith(previous):
        return current[len(previous):].lstrip("\n")
    previous_lines = [line for line in previous.splitlines() if line.strip()]
    current_lines = [line for line in current.splitlines() if line.strip()]
    if len(current_lines) > len(previous_lines) and current_lines[:len(previous_lines)] == previous_lines:
        return "\n".join(current_lines[len(previous_lines):])
    return current if current != previous else ""


def _tool_create_document(args: Dict[str, Any], **_: Any) -> str:
    title = str(args.get("title") or "Untitled").strip() or "Untitled"
    body = str(args.get("body") or args.get("markdown") or "")
    block_json = _normalize_block_json(args.get("block_json"), title=title, body=body)
    action = {
        "operation": "create",
        "attach_to_session": bool(args.get("attach_to_session", True)),
        "input": {
            "title": title,
            "block_json": block_json,
            "created_by": "agent",
        },
    }
    fields = args.get("fields") if isinstance(args.get("fields"), dict) else {}
    fields = _merge_ui_templates_into_fields(args, fields)
    if fields:
        action["input"]["fields"] = fields
    _queue_action(action)
    return _queued_result("create", action)


def _tool_update_document(args: Dict[str, Any], **_: Any) -> str:
    document_id = str(args.get("document_id") or "").strip()
    command = str(args.get("command") or "overwrite").strip()
    input_payload: Dict[str, Any]
    if command == "append_blocks":
        blocks = args.get("blocks")
        if not isinstance(blocks, list):
            body = str(args.get("body") or args.get("markdown") or "")
            blocks = _block_json_from_text(body=body).get("blocks", [])
        input_payload = {"command": "append_blocks", "blocks": blocks, "updated_by": "agent"}
    elif command == "patch_fields":
        input_payload = {"command": "patch_fields", "updated_by": "agent"}
        if args.get("title"):
            input_payload["title"] = str(args["title"])
        fields = args.get("fields") if isinstance(args.get("fields"), dict) else {}
        fields = _merge_ui_templates_into_fields(args, fields)
        if fields:
            input_payload["fields"] = fields
    else:
        title = str(args.get("title") or "").strip()
        body = str(args.get("body") or args.get("markdown") or "")
        input_payload = {
            "command": "overwrite",
            "block_json": _normalize_block_json(args.get("block_json"), title=title, body=body),
            "updated_by": "agent",
        }
        if title:
            input_payload["title"] = title
        fields = args.get("fields") if isinstance(args.get("fields"), dict) else {}
        fields = _merge_ui_templates_into_fields(args, fields)
        if fields:
            input_payload["fields"] = fields
    action: Dict[str, Any] = {"operation": "update", "input": input_payload}
    if document_id:
        action["document_id"] = document_id
    _queue_action(action)
    return _queued_result("update", action)


def _tool_delete_document(args: Dict[str, Any], **_: Any) -> str:
    document_id = str(args.get("document_id") or "").strip()
    action: Dict[str, Any] = {"operation": "delete"}
    if document_id:
        action["document_id"] = document_id
    _queue_action(action)
    return _queued_result("delete", action)


def _tool_get_document(args: Dict[str, Any], **_: Any) -> str:
    context = _active_tool_context()
    document_id = str(args.get("document_id") or context.get("document_id") or "").strip()
    session_id = str(args.get("session_id") or context.get("session_id") or "").strip()
    query: Dict[str, Any] = {
        "view": str(args.get("view") or "summary").strip() or "summary",
    }
    for key in ("field", "start", "block_limit", "char_limit"):
        value = args.get(key)
        if value is not None and value != "":
            query[key] = value
    query_string = f"?{parse.urlencode(query)}" if query else ""
    if document_id:
        path = f"/api/docs/{parse.quote(document_id, safe='')}"
    elif session_id:
        path = f"/api/sessions/{parse.quote(session_id, safe='')}/document"
    else:
        raise RuntimeError("xiaoduiyou_documents_get requires document_id or an active Xiaoduiyou session")
    result = _request_json(
        f"{context['base_url']}{path}{query_string}",
        timeout=DEFAULT_TIMEOUT_SECONDS,
        token=context["token"],
    )
    return json.dumps({"ok": True, "context": _safe_tool_context(context), "document": result}, ensure_ascii=False)


def _tool_im_send(args: Dict[str, Any], **_: Any) -> str:
    context = _active_tool_context()
    session_id = str(args.get("session_id") or context.get("session_id") or "").strip()
    turn_id = str(args.get("turn_id") or context.get("turn_id") or "").strip()
    content = args.get("content")
    if not isinstance(content, list) or not content:
        raise RuntimeError("xiaoduiyou_im_send requires content[] with input_text/input_image parts")
    result = _request_json(
        f"{context['base_url']}/api/agent/im/send",
        method="POST",
        payload={
            "session_id": session_id,
            "turn_id": turn_id,
            "content": content,
        },
        timeout=DEFAULT_TIMEOUT_SECONDS,
        token=context["token"],
    )
    attachments = result.get("image_attachments")
    return json.dumps({
        "ok": True,
        "context": _safe_tool_context(context),
        "status": result.get("status"),
        "mode": result.get("mode"),
        "message_id": result.get("message_id"),
        "attachment_count": len(attachments) if isinstance(attachments, list) else 0,
    }, ensure_ascii=False)


def _active_tool_context() -> Dict[str, Any]:
    context = _ACTIVE_XIAODUIYOU_TOOL_CONTEXT.get() or {}
    base_url = str(context.get("base_url") or _base_url_from_config() or "").rstrip("/")
    token = str(context.get("token") or _connection_token_from_config() or "").strip()
    if not base_url:
        raise RuntimeError("Xiaoduiyou tool context is missing base_url")
    if not token:
        raise RuntimeError("Xiaoduiyou connector is missing connection token; reconnect Xiaoduiyou Agent instead of asking the model to find a token")
    next_context = dict(context)
    next_context["base_url"] = base_url
    next_context["token"] = token
    return next_context


def _growth_diary_query_string(context: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> str:
    query: Dict[str, Any] = dict(params or {})
    for key in ("turn_id", "session_id"):
        value = str(context.get(key) or "").strip()
        if value and key not in query:
            query[key] = value
    return f"?{parse.urlencode(query)}" if query else ""


def _tool_growth_diary_get(args: Dict[str, Any], **_: Any) -> str:
    context = _active_tool_context()
    filter_spec = _growth_diary_filter_spec(args)
    view = str(args.get("view") or "").strip()
    record_query = _growth_diary_records_query(args, filter_spec, view)
    query_string = _growth_diary_query_string(context, record_query)
    result = _request_json(
        f"{context['base_url']}/api/growth-diary{query_string}",
        timeout=DEFAULT_TIMEOUT_SECONDS,
        token=context["token"],
    )
    if filter_spec and record_query.get("view") != "records":
        result = _compact_growth_diary_result(result, filter_spec)
    return json.dumps({"ok": True, "context": _safe_tool_context(context), "filter": filter_spec or None, "growth_diary": result}, ensure_ascii=False)


def _growth_diary_records_query(args: Dict[str, Any], filter_spec: Dict[str, Any], view: str) -> Dict[str, Any]:
    event_type = str(args.get("event_type") or "").strip()
    query = str(args.get("query") or args.get("q") or "").strip()
    unit = str(args.get("unit") or "").strip()
    quantity = args.get("quantity")
    has_record_filter = bool(filter_spec or event_type or query or unit or quantity is not None)
    if view != "records" and (view == "full" or not has_record_filter):
        return {}
    params: Dict[str, Any] = {"view": "records", **filter_spec}
    if event_type:
        params["event_type"] = event_type
    if query:
        params["query"] = query
    if unit:
        params["unit"] = unit
    if quantity is not None:
        params["quantity"] = quantity
    return params


def _growth_diary_filter_spec(args: Dict[str, Any]) -> Dict[str, Any]:
    date = str(args.get("date") or "").strip()
    start_date = str(args.get("start_date") or args.get("from_date") or "").strip()
    end_date = str(args.get("end_date") or args.get("to_date") or "").strip()
    record_limit_raw = args.get("record_limit", args.get("limit", 80))
    try:
        record_limit = int(record_limit_raw)
    except Exception:
        record_limit = 80
    record_limit = max(1, min(record_limit, 500))
    if date:
        start_date = date
        end_date = date
    spec: Dict[str, Any] = {"record_limit": record_limit}
    if start_date:
        spec["start_date"] = start_date[:10]
    if end_date:
        spec["end_date"] = end_date[:10]
    # Without a date/range/explicit cap, preserve legacy full GET behavior.
    if not (date or start_date or end_date or "record_limit" in args or "limit" in args):
        return {}
    return spec


def _compact_growth_diary_result(result: Any, filter_spec: Dict[str, Any]) -> Any:
    if not isinstance(result, dict):
        return result
    base = result.get("base")
    if not isinstance(base, dict):
        return result
    next_base = dict(base)
    next_tables = []
    total_before = 0
    total_after = 0
    table_list = base.get("tables")
    if not isinstance(table_list, list):
        table_list = []
    for table in table_list:
        if not isinstance(table, dict):
            next_tables.append(table)
            continue
        table_records = table.get("records")
        records: List[Any] = table_records if isinstance(table_records, list) else []
        total_before += len(records)
        filtered = _filter_growth_diary_records(records, filter_spec)
        total_after += len(filtered)
        next_table = dict(table)
        next_table["records"] = filtered
        next_table["records_filtered"] = {
            "total_before_filter": len(records),
            "returned": len(filtered),
            "filter": filter_spec,
        }
        next_tables.append(next_table)
    next_base["tables"] = next_tables
    return {
        **result,
        "base": next_base,
        "compact": True,
        "records_filtered": {
            "total_before_filter": total_before,
            "returned": total_after,
            "filter": filter_spec,
        },
    }


def _filter_growth_diary_records(records: List[Any], filter_spec: Dict[str, Any]) -> List[Any]:
    start_date = str(filter_spec.get("start_date") or "")[:10]
    end_date = str(filter_spec.get("end_date") or "")[:10]
    limit = int(filter_spec.get("record_limit") or 80)
    filtered: List[Any] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        record_date = _growth_diary_record_date(record)
        if start_date and (not record_date or record_date < start_date):
            continue
        if end_date and (not record_date or record_date > end_date):
            continue
        filtered.append(record)
    filtered.sort(key=lambda record: (_growth_diary_record_datetime(record), str(record.get("record_id") or "")))
    return filtered[:limit]


def _growth_diary_record_date(record: Dict[str, Any]) -> str:
    raw_values = record.get("values")
    values: Dict[str, Any] = raw_values if isinstance(raw_values, dict) else {}
    for key in ("date", "occurred_at"):
        value = _growth_diary_value_to_string(values.get(key))
        if value:
            return value[:10]
    for key in ("date", "occurred_at", "created_at", "updated_at"):
        value = str(record.get(key) or "").strip()
        if value:
            return value[:10]
    return ""


def _growth_diary_record_datetime(record: Dict[str, Any]) -> str:
    raw_values = record.get("values")
    values: Dict[str, Any] = raw_values if isinstance(raw_values, dict) else {}
    occurred_at = _growth_diary_value_to_string(values.get("occurred_at"))
    date = _growth_diary_value_to_string(values.get("date")) or _growth_diary_record_date(record)
    if occurred_at:
        return occurred_at if "T" in occurred_at or " " in occurred_at else f"{date} {occurred_at}"
    return date


def _growth_diary_value_to_string(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("value", "date", "datetime"):
            raw = value.get(key)
            if raw is not None:
                return str(raw).strip()
        if value.get("type") == "number" and value.get("value") is not None:
            return str(value.get("value")).strip()
        return ""
    if value is None:
        return ""
    return str(value).strip()


def _growth_diary_record_summary(record: Any) -> Dict[str, Any]:
    record_dict: Dict[str, Any] = record if isinstance(record, dict) else {}
    raw_values = record_dict.get("values")
    values: Dict[str, Any] = raw_values if isinstance(raw_values, dict) else {}
    return {
        "record_id": record_dict.get("record_id"),
        "source": record_dict.get("source"),
        "date": _growth_diary_value_to_string(values.get("date")),
        "occurred_at": _growth_diary_value_to_string(values.get("occurred_at")),
        "event_type": _growth_diary_value_to_string(values.get("event_type")),
        "title": _growth_diary_value_to_string(values.get("title")),
        "content": _growth_diary_value_to_string(values.get("content")),
        "quantity": _growth_diary_value_to_string(values.get("quantity")),
        "unit": _growth_diary_value_to_string(values.get("unit")),
        "risk": _growth_diary_value_to_string(values.get("risk")),
        "updated_at": record_dict.get("updated_at"),
    }


def _summarize_growth_diary_patch_result(payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
    result_dict: Dict[str, Any] = result if isinstance(result, dict) else {}
    base = result_dict.get("base") if isinstance(result_dict.get("base"), dict) else {}
    tables = base.get("tables") if isinstance(base.get("tables"), list) else []
    updated_at = str(base.get("updated_at") or "").strip()
    requested_records = payload.get("records") if isinstance(payload.get("records"), list) else []
    requested_updates = payload.get("updates") if isinstance(payload.get("updates"), list) else []
    requested_deletions = payload.get("deletions") if isinstance(payload.get("deletions"), list) else []
    requested_field_options = payload.get("field_options") if isinstance(payload.get("field_options"), list) else []
    requested_views = payload.get("views") if isinstance(payload.get("views"), list) else []

    table_summaries: List[Dict[str, Any]] = []
    changed_record_ids = {
        str(item.get("record_id") or "")
        for item in [*requested_updates, *requested_deletions]
        if isinstance(item, dict) and item.get("record_id")
    }
    created_records: List[Dict[str, Any]] = []
    changed_records: List[Dict[str, Any]] = []
    deletion_results: List[Dict[str, Any]] = [
        {
            "table_id": item.get("table_id") if isinstance(item, dict) else None,
            "record_id": item.get("record_id") if isinstance(item, dict) else None,
            "deleted": True,
        }
        for item in requested_deletions
    ]

    for table in tables:
        if not isinstance(table, dict):
            continue
        records = table.get("records") if isinstance(table.get("records"), list) else []
        table_summaries.append({
            "table_id": table.get("table_id"),
            "record_count": len(records),
            "updated_at": table.get("updated_at"),
        })
        for record in records:
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("record_id") or "")
            if record_id in changed_record_ids:
                changed_records.append(_growth_diary_record_summary(record))
            if record_id not in changed_record_ids and requested_records and str(record.get("updated_at") or "") == updated_at:
                created_records.append(_growth_diary_record_summary(record))
        for deletion_result in deletion_results:
            if deletion_result.get("table_id") != table.get("table_id"):
                continue
            deletion_result["deleted"] = not any(
                isinstance(record, dict) and record.get("record_id") == deletion_result.get("record_id")
                for record in records
            )

    return {
        "ok": True,
        "summary": {
            "updated_at": updated_at or None,
            "tables": table_summaries,
            "requested": {
                "records": len(requested_records),
                "updates": len(requested_updates),
                "deletions": len(requested_deletions),
                "field_options": len(requested_field_options),
                "views": len(requested_views),
            },
            "created_records": created_records[:max(5, len(requested_records))],
            "changed_records": changed_records[:max(5, len(requested_updates))],
            "deletion_results": deletion_results,
            "note": "PATCH succeeded. This is a concise verification summary; the full Growth Diary base is intentionally omitted to avoid Hermes output truncation.",
        },
    }


def _growth_diary_patch_failure_result(exc: Exception) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": str(exc),
        "skill": "xiaoduiyou-growth-diary",
        "hint": (
            "Read/use skill xiaoduiyou-growth-diary, then retry with payload.records[].table_id "
            "and source at the record root, and field values inside records[].values. Example: "
            "{ records: [{ table_id: 'tbl_growth_events', source: 'agent', values: { title: '喝奶 150ml', "
            "event_type: 'milk', quantity: 150, unit: 'ml' } }] }. Use updates for existing cells and deletions for deletes."
        ),
    }


def _tool_growth_diary_patch(args: Dict[str, Any], **_: Any) -> str:
    context = _active_tool_context()
    payload = args.get("payload")
    if payload is None:
        payload = {key: value for key, value in args.items() if key not in {"payload"}}
    if not isinstance(payload, dict):
        raise RuntimeError("payload must be an object matching /api/growth-diary PATCH")
    try:
        query_string = _growth_diary_query_string(context)
        result = _request_json(
            f"{context['base_url']}/api/growth-diary{query_string}",
            method="PATCH",
            payload=payload,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            token=context["token"],
        )
    except Exception as exc:
        return json.dumps({
            "ok": False,
            "context": _safe_tool_context(context),
            "result": _growth_diary_patch_failure_result(exc),
        }, ensure_ascii=False)
    return json.dumps({
        "ok": True,
        "context": _safe_tool_context(context),
        "result": _summarize_growth_diary_patch_result(payload, result),
    }, ensure_ascii=False)


def _safe_tool_context(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "base_url": context.get("base_url"),
        "environment": context.get("environment"),
        "home_id": context.get("home_id"),
        "family_id": context.get("family_id"),
        "session_id": context.get("session_id"),
        "turn_id": context.get("turn_id"),
        "document_id": context.get("document_id"),
        "auth": "connector_token_bound",
    }


async def _standalone_send(
    pconfig,
    chat_id: str,
    message: str,
    *,
    thread_id=None,
    media_files=None,
    force_document: bool = False,
) -> Dict[str, Any]:
    del thread_id, media_files, force_document
    adapter = XiaoduiyouAdapter(pconfig)
    result = await adapter.send(chat_id=chat_id, content=message)
    if result.success:
        return {"success": True, "message_id": result.message_id, "raw_response": result.raw_response}
    return {"error": result.error or "Xiaoduiyou delivery failed"}


def register(ctx) -> None:
    ctx.register_platform(
        name="xiaoduiyou",
        label="Xiaoduiyou",
        adapter_factory=lambda cfg: XiaoduiyouAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        required_env=[],
        install_hint="Set platforms.xiaoduiyou.extra.base_url or XIAODUIYOU_BASE_URL.",
        emoji="📝",
        platform_hint=(
            "Xiaoduiyou is a document workspace. Use normal chat for ordinary replies. "
            "Only call xiaoduiyou document tools when the user explicitly asks for a document artifact or mutation. "
            "Content packages may select ui_templates (xiaohongshu, moments) and fill fields.publish_notes for those templates."
        ),
        max_message_length=XiaoduiyouAdapter.MAX_MESSAGE_LENGTH,
        cron_deliver_env_var="XIAODUIYOU_HOME_CHANNEL",
        standalone_sender_fn=_standalone_send,
    )

    ctx.register_tool(
        name="xiaoduiyou_growth_diary_get",
        toolset=TOOLSET,
        description="Read Xiaoduiyou Growth Diary data through the connector-owned origin/token for the current Xiaoduiyou turn. Use skill xiaoduiyou-growth-diary before writes.",
        emoji="📖",
        schema={
            "name": "xiaoduiyou_growth_diary_get",
            "description": "Read Growth Diary data for the current Xiaoduiyou home. Use skill xiaoduiyou-growth-diary. To find a record_id before update/delete, pass date/event_type/query/quantity/unit; filtered calls default to view=records and return concise records instead of the full base. Do not search for connection_token manually.",
            "parameters": {
                "type": "object",
                "properties": {
                    "view": {"type": "string", "enum": ["full", "records"], "description": "Use records to return a concise record_id-friendly list. Omit for full legacy base only when schema/options/views are needed."},
                    "date": {"type": "string", "description": "Optional YYYY-MM-DD date. When present, the connector defaults to view=records."},
                    "start_date": {"type": "string", "description": "Optional inclusive YYYY-MM-DD range start."},
                    "end_date": {"type": "string", "description": "Optional inclusive YYYY-MM-DD range end."},
                    "event_type": {"type": "string", "description": "Optional event type option id such as milk, poop, food, height, weight, note."},
                    "query": {"type": "string", "description": "Optional text query matched against title/content/original_message/recorder. Use this to find a record_id before deletion."},
                    "quantity": {"type": "number", "description": "Optional numeric quantity filter, such as 150."},
                    "unit": {"type": "string", "description": "Optional unit option id such as ml, times, kg, cm."},
                    "record_limit": {"type": "integer", "description": "Maximum records to return after filtering. Defaults to 80 when any filter is used; capped at 500."},
                },
            },
        },
        handler=_tool_growth_diary_get,
        check_fn=check_requirements,
    )
    ctx.register_tool(
        name="xiaoduiyou_growth_diary_patch",
        toolset=TOOLSET,
        description="Patch Xiaoduiyou Growth Diary data through the connector-owned origin/token for the current Xiaoduiyou turn. Use skill xiaoduiyou-growth-diary and call get first.",
        emoji="🍼",
        schema={
            "name": "xiaoduiyou_growth_diary_patch",
            "description": "Create/update/delete Growth Diary records/options/views for the current Xiaoduiyou home. The connector supplies auth; the model must pass only the PATCH payload. Use skill xiaoduiyou-growth-diary first. For new records, records items must look like { table_id, source, values }; put title/event_type/quantity/unit/date/occurred_at/risk inside values, not at the record root. For records with source='agent', values.date is required as YYYY-MM-DD and values.occurred_at is required as YYYY-MM-DD HH:mm:ss; short times like 19:20 are rejected, and occurred_at must use the same date as date. Use updates for existing cells, deletions for deletes, and never send values:null. The result is a concise verification summary, not the full base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payload": {"type": "object", "description": "Exact JSON payload for PATCH /api/growth-diary after reading the live schema and using skill xiaoduiyou-growth-diary. Use records only to add records; each record must have table_id/source at the record root and field values under values, e.g. { records: [{ table_id: 'tbl_growth_events', source: 'agent', values: { date: '2026-06-09', occurred_at: '2026-06-09 19:20:00', event_type, title, content, quantity, unit, risk } }] }. Agent-created records must set values.date='YYYY-MM-DD' and values.occurred_at='YYYY-MM-DD HH:mm:ss' with matching dates; do not send time-only values. Use updates for existing cells, deletions for deletes, and never send values:null."},
                },
                "required": ["payload"],
            },
        },
        handler=_tool_growth_diary_patch,
        check_fn=check_requirements,
    )

    ctx.register_tool(
        name="xiaoduiyou_documents_get",
        toolset=TOOLSET,
        description="Read the current Xiaoduiyou content-package document concisely through the connector-owned origin/token.",
        emoji="📄",
        schema={
            "name": "xiaoduiyou_documents_get",
            "description": "Read Xiaoduiyou content-package documents without loading everything by default. Omit document_id/session_id inside an active Xiaoduiyou turn to read the current session document. Default view=summary. Use view=field for one field such as publish_notes.xiaohongshu/source_markdown, view=blocks for paged blocks, and view=full only when explicitly necessary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Optional document id. Use when known."},
                    "session_id": {"type": "string", "description": "Optional Xiaoduiyou session id. Omit to read the current Xiaoduiyou turn's attached document."},
                    "view": {"type": "string", "enum": ["summary", "field", "blocks", "full"], "description": "Default summary is concise. Use field for one metadata field, blocks for paged block_json, and full only when explicitly needed."},
                    "field": {"type": "string", "description": "Required for view=field. Dot path under fields, e.g. publish_notes.xiaohongshu or source_markdown."},
                    "start": {"type": "integer", "description": "For view=blocks: zero-based block offset."},
                    "block_limit": {"type": "integer", "description": "For summary/blocks: max blocks/previews returned."},
                    "char_limit": {"type": "integer", "description": "For view=field: max string/JSON preview chars."},
                },
            },
        },
        handler=_tool_get_document,
        check_fn=check_requirements,
    )

    ctx.register_tool(
        name="xiaoduiyou_documents_create",
        toolset=TOOLSET,
        description="Queue creation of a Xiaoduiyou document for the current Xiaoduiyou turn.",
        emoji="📝",
        schema={
            "name": "xiaoduiyou_documents_create",
            "description": "Create a Xiaoduiyou document only when the user explicitly asks for a document artifact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Document title."},
                    "body": {"type": "string", "description": "Plain text or Markdown body. One paragraph per line is OK."},
                    "block_json": {"type": "object", "description": "Optional Xiaoduiyou Block JSON: {schema:'xdy.block_json.v1', blocks:[...]}"},
                    "ui_templates": {
                        "type": "array",
                        "description": "Content-package UI templates to render. Currently supported: xiaohongshu and moments. Also written to fields.ui_templates.",
                        "items": {"type": "string", "enum": ["xiaohongshu", "moments"]},
                    },
                    "fields": {"type": "object", "description": "Optional metadata fields."},
                    "attach_to_session": {"type": "boolean", "description": "Attach as the current session document. Defaults true."},
                },
                "required": ["title"],
            },
        },
        handler=_tool_create_document,
        check_fn=check_requirements,
    )
    ctx.register_tool(
        name="xiaoduiyou_documents_update",
        toolset=TOOLSET,
        description="Queue update of an existing/current Xiaoduiyou document for the current Xiaoduiyou turn.",
        emoji="✏️",
        schema={
            "name": "xiaoduiyou_documents_update",
            "description": "Update a Xiaoduiyou document only when the user explicitly asks to modify a document. Omit document_id to target the current screen document/content package; Xiaoduiyou falls back to the current session document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Optional document id. If omitted, Xiaoduiyou updates the current screen document/content package, then falls back to the current session document."},
                    "command": {"type": "string", "enum": ["overwrite", "append_blocks", "patch_fields"], "description": "Update mode. Defaults overwrite."},
                    "title": {"type": "string", "description": "New title for overwrite or patch_fields."},
                    "body": {"type": "string", "description": "New/append body text."},
                    "block_json": {"type": "object", "description": "Optional full Block JSON for overwrite."},
                    "ui_templates": {
                        "type": "array",
                        "description": "Replace the content-package UI templates for this document. Currently supported: xiaohongshu and moments. Also written to fields.ui_templates.",
                        "items": {"type": "string", "enum": ["xiaohongshu", "moments"]},
                    },
                    "blocks": {
                        "type": "array",
                        "description": "Blocks for append_blocks.",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                    "fields": {"type": "object", "description": "Metadata fields for patch_fields/overwrite."},
                },
            },
        },
        handler=_tool_update_document,
        check_fn=check_requirements,
    )
    ctx.register_tool(
        name="xiaoduiyou_documents_delete",
        toolset=TOOLSET,
        description="Queue deletion of a Xiaoduiyou document for the current Xiaoduiyou turn.",
        emoji="🗑️",
        schema={
            "name": "xiaoduiyou_documents_delete",
            "description": "Delete a Xiaoduiyou document only when the user explicitly asks to delete a document. Omit document_id to target the current screen document/content package; Xiaoduiyou falls back to the current session document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Optional document id. If omitted, Xiaoduiyou deletes the current screen document/content package, then falls back to the current session document."},
                },
            },
        },
        handler=_tool_delete_document,
        check_fn=check_requirements,
    )
    ctx.register_tool(
        name="xiaoduiyou_im_send",
        toolset=TOOLSET,
        description="Send Xiaoduiyou chat image cards using OpenAI Responses-style content parts. Use input_text and input_image; backend uploads images and creates image_attachments.",
        emoji="🖼️",
        schema={
            "name": "xiaoduiyou_im_send",
            "description": "Send Xiaoduiyou IM visual cards. Use OpenAI Responses-style content parts: input_text for text, input_image for image cards. image_url must be HTTPS or data:image/png|jpeg|webp|gif;base64,... . Never pass local file paths, file:, blob:, localhost, or private-network URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Optional Xiaoduiyou session id. Omit inside an active Xiaoduiyou turn."},
                    "turn_id": {"type": "string", "description": "Optional Xiaoduiyou turn id. Omit inside an active Xiaoduiyou turn."},
                    "content": {
                        "type": "array",
                        "description": "OpenAI Responses-style content parts.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["input_text", "input_image"]},
                                "text": {"type": "string", "description": "Text for input_text parts."},
                                "image_url": {"type": "string", "description": "HTTPS image URL or data:image/...;base64,... for input_image parts."},
                                "detail": {"type": "string", "enum": ["auto", "low", "high"], "description": "Responses-style image detail hint."},
                                "display": {
                                    "type": "object",
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
                },
                "required": ["content"],
            },
        },
        handler=_tool_im_send,
        check_fn=check_requirements,
    )
