from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ADAPTER_PATH = ROOT / "plugins" / "xiaoduiyou-hermes-platform" / "xiaoduiyou_hermes_platform" / "adapter.py"


def _install_gateway_stubs() -> None:
    gateway = types.ModuleType("gateway")
    config = types.ModuleType("gateway.config")
    platforms = types.ModuleType("gateway.platforms")
    base = types.ModuleType("gateway.platforms.base")
    session = types.ModuleType("gateway.session")

    class Platform(str):
        pass

    class PlatformConfig:
        def __init__(self, *, extra=None):
            self.extra = extra or {}

    class BasePlatformAdapter:
        def __init__(self, *, config, platform):
            self.config = config
            self.platform = platform
            self._running = False
            self.marked_connected = False
            self.marked_disconnected = False

        def _mark_connected(self):
            self.marked_connected = True
            self.marked_disconnected = False

        def _mark_disconnected(self):
            self.marked_disconnected = True

        async def handle_message(self, event):
            self.last_message_event = event

    class MessageEvent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class MessageType:
        COMMAND = "command"
        PHOTO = "photo"
        TEXT = "text"

    class SendResult:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class SessionSource:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    config.Platform = Platform
    config.PlatformConfig = PlatformConfig
    base.BasePlatformAdapter = BasePlatformAdapter
    base.MessageEvent = MessageEvent
    base.MessageType = MessageType
    base.SendResult = SendResult
    session.SessionSource = SessionSource

    sys.modules.setdefault("gateway", gateway)
    sys.modules["gateway.config"] = config
    sys.modules.setdefault("gateway.platforms", platforms)
    sys.modules["gateway.platforms.base"] = base
    sys.modules["gateway.session"] = session


def _load_adapter():
    _install_gateway_stubs()
    spec = importlib.util.spec_from_file_location("xiaoduiyou_adapter_under_test", ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter()


def _server_frame(opcode: int, payload: bytes = b"") -> bytes:
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        return bytes([first, length]) + payload
    if length < 65536:
        return bytes([first, 126]) + adapter.struct.pack("!H", length) + payload
    return bytes([first, 127]) + adapter.struct.pack("!Q", length) + payload


class _FakeWriter:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    async def drain(self) -> None:
        return None


class DeliveryClassificationTests(unittest.TestCase):
    def test_hermes_help_listing_is_not_tool_progress(self):
        content = "\n".join([
            "📖 **Hermes Commands**",
            "",
            "`/start` -- Acknowledge platform start pings without a reply",
            "`/new [name]` -- Start a new session (fresh session ID + history)",
        ])

        self.assertFalse(adapter._looks_like_tool_progress(content))

    def test_command_listing_without_header_is_not_tool_progress(self):
        content = "\n".join([
            "`/usage` -- Show token usage and rate limits for the current session",
            "`/debug` -- Upload debug report (system info + logs)",
        ])

        self.assertFalse(adapter._looks_like_tool_progress(content))

    def test_tool_progress_still_uses_icon_heuristic(self):
        self.assertTrue(adapter._looks_like_tool_progress('📖 read_file: "package.json"'))

    def test_asset_upload_tool_progress_uses_attachment_icon(self):
        self.assertTrue(adapter._looks_like_tool_progress('📎 xiaoduiyou_assets_upload(file_path="/tmp/card.png")'))

    def test_mini_app_contract_tool_progress_uses_puzzle_icon(self):
        self.assertTrue(adapter._looks_like_tool_progress("🧩 xiaoduiyou_mini_app_contract_get()"))

    def test_all_hermes_friendly_tool_labels_are_tool_progress(self):
        messages = (
            "🔍 Searching the web for Hermes tool labels",
            "🌐 Reading https://example.com/docs",
            "🌐 Browsing https://example.com",
            "👆 Clicking Submit",
            "⌨️ Typing hello",
            "📖 Reading README.md",
            "📄 Writing report.md",
            "✏️ Editing src/app.ts",
            "🔎 Searching files for actionInProgress",
            "💻 Running pnpm test",
            "🐍 Running code print('ok')",
            "🎨 Generating image a family portrait",
            "🎬 Generating video a short clip",
            "🔊 Generating speech hello",
            "👁️ Looking at the image screenshot.png",
            "🔎 Searching past sessions",
            "📚 Reading skill diagnose",
            "📚 Listing skills",
            "📚 Updating skill diagnose",
            "👥 Delegating inspect the adapter",
            "⏰ Scheduling daily report",
            "❓ Asking for confirmation",
            "🧠 Updating memory preferences",
            "📋 Updating tasks",
        )

        for message in messages:
            with self.subTest(message=message):
                self.assertTrue(adapter._looks_like_tool_progress(message))


class ContentPackageTemplateTests(unittest.TestCase):
    def test_normalize_ui_templates_preserves_all_supported_templates(self):
        templates = adapter._normalize_ui_templates([
            "xiaohongshu",
            "moments",
            "travel_plan",
            "interactive_html",
            "mini_app",
            "mini_app",
            "unknown",
        ])

        self.assertEqual(
            templates,
            ["xiaohongshu", "moments", "travel_plan", "interactive_html", "mini_app"],
        )

    def test_mini_app_contract_tool_returns_live_v2_vocabulary(self):
        old_active_tool_context = adapter._active_tool_context
        old_request_json = adapter._request_json
        calls = []

        def fake_context():
            return {"base_url": "https://review.example.test", "token": "token", "session_id": "sess_1"}

        def return_contract(url, **kwargs):
            calls.append({"url": url, **kwargs})
            return {
                "contract": {
                    "schema": "xdy.mini_app.v2",
                    "runtime_version": "2.0",
                    "actions": ["state.set", "navigate"],
                    "components": ["text", "button"],
                }
            }

        adapter._active_tool_context = fake_context
        adapter._request_json = return_contract
        try:
            result = json.loads(adapter._tool_mini_app_contract_get({}))
        finally:
            adapter._active_tool_context = old_active_tool_context
            adapter._request_json = old_request_json

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["contract"]["schema"], "xdy.mini_app.v2")
        self.assertEqual(result["context"]["session_id"], "sess_1")
        self.assertEqual(calls[0]["url"], "https://review.example.test/api/mini-apps/contract")
        self.assertEqual(calls[0]["token"], "token")

    def test_adapter_prompts_strict_v2_and_never_v1(self):
        source = ADAPTER_PATH.read_text(encoding="utf-8")

        self.assertIn("xiaoduiyou_mini_app_contract_get", source)
        self.assertIn("mini_app_path", source)
        self.assertIn("schema xdy.mini_app.v2", source)
        self.assertNotIn("schema xdy.mini_app.v1", source)

    def test_create_document_loads_large_mini_app_from_json_path(self):
        old_active_tool_context = adapter._active_tool_context
        old_request_json = adapter._request_json
        calls = []
        definition = {
            "schema": "xdy.mini_app.v2",
            "manifest": {"title": "任务板", "entry_page": "home", "min_runtime": "2.0", "capabilities": []},
            "data": {},
            "state": {},
            "computed": {},
            "actions": {},
            "resources": {},
            "pages": {"home": {"root": {"type": "text", "value": "ready"}}},
        }

        def fake_context():
            return {"base_url": "https://review.example.test", "token": "token", "session_id": "sess_1"}

        def capture_request(url, **kwargs):
            calls.append({"url": url, **kwargs})
            return {"document": {"document_id": "doc_1", "title": "任务板"}}

        adapter._active_tool_context = fake_context
        adapter._request_json = capture_request
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "xdy-mini-app-task-board.json"
                path.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
                result = json.loads(adapter._tool_create_document({
                    "title": "任务板",
                    "mini_app_path": str(path),
                }))
        finally:
            adapter._active_tool_context = old_active_tool_context
            adapter._request_json = old_request_json

        self.assertEqual(result["ok"], True)
        self.assertEqual(calls[0]["payload"]["fields"]["ui_templates"], ["mini_app"])
        self.assertEqual(calls[0]["payload"]["fields"]["ui_payloads"]["mini_app"], definition)

    def test_mini_app_path_rejects_v1_and_hidden_home_paths(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as directory:
            hidden = Path(directory) / ".private"
            hidden.mkdir()
            path = hidden / "mini-app.json"
            path.write_text(json.dumps({"schema": "xdy.mini_app.v2"}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "hidden directory"):
                adapter._read_mini_app_path({"mini_app_path": str(path)})

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mini-app.json"
            path.write_text(json.dumps({"schema": "xdy.mini_app.v1"}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "xdy.mini_app.v2"):
                adapter._read_mini_app_path({"mini_app_path": str(path)})

    def test_update_document_loads_mini_app_path_for_patch_fields(self):
        old_active_tool_context = adapter._active_tool_context
        old_request_json = adapter._request_json
        calls = []
        definition = {
            "schema": "xdy.mini_app.v2",
            "manifest": {"title": "任务板", "entry_page": "home", "min_runtime": "2.0", "capabilities": []},
            "data": {},
            "state": {},
            "computed": {},
            "actions": {},
            "resources": {},
            "pages": {"home": {"root": {"type": "text", "value": "updated"}}},
        }

        def fake_context():
            return {"base_url": "https://review.example.test", "token": "token", "session_id": "sess_1"}

        def capture_request(url, **kwargs):
            calls.append({"url": url, **kwargs})
            return {
                "mutation": {"mutation_id": "mut_1", "state": "persisted", "target_document_id": "doc_1"},
                "document": {"document_id": "doc_1", "title": "任务板"},
            }

        adapter._active_tool_context = fake_context
        adapter._request_json = capture_request
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "xdy-mini-app-task-board.json"
                path.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
                result = json.loads(adapter._tool_update_document({
                    "document_id": "doc_1",
                    "command": "patch_fields",
                    "mini_app_path": str(path),
                }))
        finally:
            adapter._active_tool_context = old_active_tool_context
            adapter._request_json = old_request_json

        self.assertEqual(result["ok"], True)
        self.assertEqual(calls[0]["payload"]["command"], "patch_fields")
        self.assertEqual(calls[0]["payload"]["fields"]["ui_templates"], ["mini_app"])
        self.assertEqual(calls[0]["payload"]["fields"]["ui_payloads"]["mini_app"], definition)

    def test_create_document_returns_mini_app_validation_as_structured_tool_result(self):
        old_active_tool_context = adapter._active_tool_context
        old_request_json = adapter._request_json

        def fake_context():
            return {"base_url": "https://review.example.test", "token": "token"}

        def reject_invalid_definition(*args, **kwargs):
            del args, kwargs
            raise RuntimeError(
                'HTTP 400: {"error":"INVALID_MINI_APP_DEFINITION","capability_available":true,'
                '"expected_schema":"xdy.mini_app.v2",'
                '"path":"fields.ui_payloads.mini_app.pages.home.root.children[0].action",'
                '"reason":"button.action must name a declared action",'
                '"expected":["save"],'
                '"skill_reference":{"reference":"skills/xiaoduiyou/xiaoduiyou-doc-content-package/references/mini-app-contract.md",'
                '"section":"Actions"}}'
            )

        adapter._active_tool_context = fake_context
        adapter._request_json = reject_invalid_definition
        try:
            result = json.loads(adapter._tool_create_document({
                "title": "坏的小程序",
                "ui_templates": ["mini_app"],
                "fields": {"ui_payloads": {"mini_app": {}}},
            }))
        finally:
            adapter._active_tool_context = old_active_tool_context
            adapter._request_json = old_request_json

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["operation"], "create")
        self.assertEqual(result["error"], "INVALID_MINI_APP_DEFINITION")
        self.assertEqual(result["expected_schema"], "xdy.mini_app.v2")
        self.assertEqual(result["path"], "fields.ui_payloads.mini_app.pages.home.root.children[0].action")
        self.assertEqual(result["skill_reference"]["section"], "Actions")

    def test_update_document_returns_mini_app_validation_as_structured_tool_result(self):
        old_active_tool_context = adapter._active_tool_context
        old_request_json = adapter._request_json

        def fake_context():
            return {"base_url": "https://review.example.test", "token": "token"}

        def reject_invalid_definition(*args, **kwargs):
            del args, kwargs
            raise RuntimeError(
                'HTTP 400: {"error":"INVALID_MINI_APP_DEFINITION","capability_available":true,'
                '"expected_schema":"xdy.mini_app.v2",'
                '"path":"fields.ui_payloads.mini_app.state.done.type",'
                '"reason":"unknown state type \\"made_up_type\\"",'
                '"expected":"string | number | boolean | string_set | string_list | object | list",'
                '"skill_reference":{"reference":"skills/xiaoduiyou/xiaoduiyou-doc-content-package/references/mini-app-contract.md",'
                '"section":"V2 payload and vocabulary"}}'
            )

        adapter._active_tool_context = fake_context
        adapter._request_json = reject_invalid_definition
        try:
            result = json.loads(adapter._tool_update_document({
                "document_id": "doc_0125",
                "command": "patch_fields",
                "fields": {"ui_payloads": {"mini_app": {}}},
            }))
        finally:
            adapter._active_tool_context = old_active_tool_context
            adapter._request_json = old_request_json

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["operation"], "update")
        self.assertEqual(result["command"], "patch_fields")
        self.assertEqual(result["document_id"], "doc_0125")
        self.assertEqual(result["path"], "fields.ui_payloads.mini_app.state.done.type")
        self.assertEqual(result["skill_reference"]["section"], "V2 payload and vocabulary")


class AssetUploadToolTests(unittest.TestCase):
    def test_upload_tool_accepts_multiple_files(self):
        calls = []
        old_active_tool_context = adapter._active_tool_context
        old_upload_asset_file_result = adapter._upload_asset_file_result

        def fake_context():
            return {"base_url": "https://review.example.test", "token": "token"}

        def fake_upload(base_url, token, path, **kwargs):
            calls.append({"base_url": base_url, "token": token, "path": path, **kwargs})
            index = len(calls)
            return {
                "url": f"https://assets.example.com/{index}.png",
                "asset": {"public_url": f"https://assets.example.com/{index}.png", "object_key": f"accounts/acct/uploads/{index}.png"},
            }

        adapter._active_tool_context = fake_context
        adapter._upload_asset_file_result = fake_upload
        try:
            result = json.loads(adapter._tool_assets_upload({
                "files": [
                    {"file_path": "/tmp/first.png", "file_name": "first.png", "mime_type": "image/png"},
                    {"file_path": "/tmp/second.jpg", "file_name": "second.jpg", "mime_type": "image/jpeg"},
                ],
                "source": "agent_generated",
            }))
        finally:
            adapter._active_tool_context = old_active_tool_context
            adapter._upload_asset_file_result = old_upload_asset_file_result

        self.assertEqual(result["uploaded_count"], 2)
        self.assertEqual(result["url"], "https://assets.example.com/1.png")
        self.assertEqual(result["urls"], ["https://assets.example.com/1.png", "https://assets.example.com/2.png"])
        self.assertEqual([call["path"] for call in calls], ["/tmp/first.png", "/tmp/second.jpg"])
        self.assertEqual([call["file_name"] for call in calls], ["first.png", "second.jpg"])
        self.assertEqual([call["mime_type"] for call in calls], ["image/png", "image/jpeg"])


class ExecApprovalTests(unittest.IsolatedAsyncioTestCase):
    async def _approval_actions(self, **capabilities):
        config = adapter.PlatformConfig(
            extra={
                "base_url": "https://review.example.test",
                "connection_token": "token",
            }
        )
        instance = adapter.XiaoduiyouAdapter(config)
        posted_payloads = []

        async def resolve_turn_id(chat_id, metadata=None):
            return "turn-1"

        async def post_interactive_request(payload):
            posted_payloads.append(payload)
            return {"request": {"request_id": ""}}

        instance._resolve_turn_id = resolve_turn_id
        instance._post_interactive_request = post_interactive_request

        result = await instance.send_exec_approval(
            chat_id="session-1",
            command="echo hello",
            session_key="gateway-session-1",
            **capabilities,
        )

        self.assertTrue(result.success)
        return posted_payloads[0]["actions"]

    async def test_exec_approval_hides_permanent_action_when_disallowed(self):
        actions = await self._approval_actions(allow_permanent=False)

        self.assertEqual(actions, ["once", "session", "deny"])

    async def test_exec_approval_hides_persistent_actions_when_session_is_disallowed(self):
        actions = await self._approval_actions(allow_session=False)

        self.assertEqual(actions, ["once", "deny"])

    async def test_exec_approval_smart_deny_only_offers_once_or_deny(self):
        actions = await self._approval_actions(smart_denied=True)

        self.assertEqual(actions, ["once", "deny"])


class ClaimedTurnTests(unittest.IsolatedAsyncioTestCase):
    def _new_adapter(self):
        config = adapter.PlatformConfig(
            extra={
                "base_url": "https://review.example.test",
                "connection_token": "token",
                "poll_interval_seconds": 0.01,
                "request_timeout_seconds": 0.01,
            }
        )
        return adapter.XiaoduiyouAdapter(config)

    async def test_image_only_turn_reaches_hermes(self):
        instance = self._new_adapter()
        image_url = "https://assets.example.test/uploads/photo.jpg"
        claimed = {
            "turn": {
                "turn_id": "turn-image-only",
                "session_id": "session-image-only",
                "user_message": "",
                "image_urls": [image_url],
                "content_parts": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
            "session": {
                "session_id": "session-image-only",
                "title": "图片咨询",
            },
        }
        original_download = adapter._download_image_attachments
        adapter._download_image_attachments = lambda urls, timeout: (
            ["/tmp/xiaoduiyou-image-only.jpg"],
            ["image/jpeg"],
        )
        try:
            await instance._handle_claimed_turn(claimed)
        finally:
            adapter._download_image_attachments = original_download

        event = instance.last_message_event
        self.assertEqual(event.message_id, "turn-image-only")
        self.assertEqual(event.message_type, adapter.MessageType.PHOTO)
        self.assertEqual(event.media_urls, ["/tmp/xiaoduiyou-image-only.jpg"])
        self.assertEqual(event.raw_message["xiaoduiyou_image_urls"], [image_url])


class TurnStreamReconnectTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        os.environ.pop("XIAODUIYOU_BASE_URL", None)
        os.environ.pop("XIAODUIYOU_CONNECTION_TOKEN", None)

    def _new_adapter(self, *, prefer_websocket: bool = True, health_probe: bool = False):
        config = adapter.PlatformConfig(
            extra={
                "base_url": "https://review.example.test",
                "connection_token": "token",
                "prefer_websocket": prefer_websocket,
                "probe_health": health_probe,
                "poll_interval_seconds": 0.01,
                "request_timeout_seconds": 0.01,
            }
        )
        instance = adapter.XiaoduiyouAdapter(config)
        instance._running = True
        return instance

    async def test_websocket_keepalive_defaults_are_enabled(self):
        instance = self._new_adapter()

        self.assertEqual(instance.websocket_ping_interval_seconds, 25.0)
        self.assertEqual(instance.websocket_ping_timeout_seconds, 10.0)

    async def test_websocket_keepalive_sends_ping_after_idle(self):
        reader = adapter.asyncio.StreamReader()
        writer = _FakeWriter()
        keepalive = adapter._WebSocketKeepalive(
            writer,
            ping_interval_seconds=0.01,
            ping_timeout_seconds=1.0,
        )
        keepalive._last_received_at = adapter.time.monotonic() - 1
        reader.feed_data(_server_frame(0x1, b'{"turn":null}'))

        message = await keepalive.read_text(reader, max_idle_seconds=1.0)

        self.assertEqual(message, '{"turn":null}')
        self.assertTrue(writer.data)
        self.assertEqual(writer.data[0] & 0x0F, 0x9)
        self.assertIsNone(keepalive._pending_ping_sent_at)

    async def test_websocket_keepalive_replies_to_server_ping(self):
        reader = adapter.asyncio.StreamReader()
        writer = _FakeWriter()
        keepalive = adapter._WebSocketKeepalive(
            writer,
            ping_interval_seconds=25.0,
            ping_timeout_seconds=10.0,
        )
        reader.feed_data(_server_frame(0x9, b"server-check"))

        message = await keepalive.read_text(reader, max_idle_seconds=1.0)

        self.assertIsNone(message)
        self.assertTrue(writer.data)
        self.assertEqual(writer.data[0] & 0x0F, 0xA)

    async def test_websocket_keepalive_times_out_pending_ping(self):
        reader = adapter.asyncio.StreamReader()
        writer = _FakeWriter()
        keepalive = adapter._WebSocketKeepalive(
            writer,
            ping_interval_seconds=25.0,
            ping_timeout_seconds=0.01,
        )
        keepalive._pending_ping_payload = b"stale"
        keepalive._pending_ping_sent_at = adapter.time.monotonic() - 1

        with self.assertRaisesRegex(adapter.XiaoduiyouWebSocketError, "keepalive ping timed out"):
            await keepalive.read_text(reader, max_idle_seconds=1.0)

    async def test_health_probe_runs_before_websocket_stream(self):
        instance = self._new_adapter(prefer_websocket=True, health_probe=True)
        calls = []

        def request_json(url, **kwargs):
            calls.append(url)
            return {"ready": True}

        async def refresh():
            return None

        async def stop_after_websocket_open():
            calls.append("websocket")
            instance._running = False

        original_request_json = adapter._request_json
        instance._refresh_channel_directory_if_due = refresh
        instance._websocket_pending_turn_loop = stop_after_websocket_open
        adapter._request_json = request_json
        try:
            await instance._turn_stream_loop()
        finally:
            adapter._request_json = original_request_json

        self.assertEqual(calls, ["https://review.example.test/api/agent/health", "websocket"])
        self.assertTrue(instance._health_endpoint_supported)

    async def test_missing_health_endpoint_falls_back_to_pending_stream(self):
        instance = self._new_adapter(prefer_websocket=True, health_probe=True)
        calls = []

        def request_json(url, **kwargs):
            calls.append(url)
            raise RuntimeError("HTTP 404: NOT_FOUND")

        async def refresh():
            return None

        async def stop_after_websocket_open():
            calls.append("websocket")
            instance._running = False

        original_request_json = adapter._request_json
        instance._refresh_channel_directory_if_due = refresh
        instance._websocket_pending_turn_loop = stop_after_websocket_open
        adapter._request_json = request_json
        try:
            await instance._turn_stream_loop()
        finally:
            adapter._request_json = original_request_json

        self.assertEqual(calls, ["https://review.example.test/api/agent/health", "websocket"])
        self.assertFalse(instance._health_endpoint_supported)
        self.assertFalse(instance.marked_disconnected)

    async def test_non_json_health_response_falls_back_to_pending_stream(self):
        instance = self._new_adapter(prefer_websocket=True, health_probe=True)
        calls = []

        def request_json(url, **kwargs):
            calls.append(url)
            raise adapter.json.JSONDecodeError("Expecting value", "<!doctype html>", 0)

        async def refresh():
            return None

        async def stop_after_websocket_open():
            calls.append("websocket")
            instance._running = False

        original_request_json = adapter._request_json
        instance._refresh_channel_directory_if_due = refresh
        instance._websocket_pending_turn_loop = stop_after_websocket_open
        adapter._request_json = request_json
        try:
            await instance._turn_stream_loop()
        finally:
            adapter._request_json = original_request_json

        self.assertEqual(calls, ["https://review.example.test/api/agent/health", "websocket"])
        self.assertFalse(instance._health_endpoint_supported)
        self.assertFalse(instance.marked_disconnected)

    async def test_health_auth_failure_stops_stream_before_websocket(self):
        instance = self._new_adapter(prefer_websocket=True, health_probe=True)
        websocket_attempts = 0

        def request_json(url, **kwargs):
            raise RuntimeError("HTTP 401: UNAUTHENTICATED")

        async def refresh():
            return None

        async def websocket_should_not_open():
            nonlocal websocket_attempts
            websocket_attempts += 1

        original_request_json = adapter._request_json
        instance._refresh_channel_directory_if_due = refresh
        instance._websocket_pending_turn_loop = websocket_should_not_open
        adapter._request_json = request_json
        try:
            await instance._turn_stream_loop()
        finally:
            adapter._request_json = original_request_json

        self.assertEqual(websocket_attempts, 0)
        self.assertFalse(instance._running)
        self.assertTrue(instance.marked_disconnected)

    async def test_websocket_failure_with_http_503_fallback_keeps_loop_alive(self):
        instance = self._new_adapter(prefer_websocket=True)
        websocket_attempts = 0
        fallback_attempts = 0
        sleeps = []

        async def refresh():
            return None

        async def fail_websocket():
            nonlocal websocket_attempts
            websocket_attempts += 1
            if websocket_attempts >= 2:
                instance._running = False
            raise adapter.XiaoduiyouWebSocketError("websocket upgrade failed: HTTP 503")

        async def fail_http_fallback(*, fallback_delay=None):
            nonlocal fallback_attempts
            fallback_attempts += 1
            raise RuntimeError("HTTP 503: review restarting")

        original_sleep = adapter.asyncio.sleep

        async def fake_sleep(delay):
            sleeps.append(delay)
            await original_sleep(0)

        instance._refresh_channel_directory_if_due = refresh
        instance._websocket_pending_turn_loop = fail_websocket
        instance._http_pending_turn_once = fail_http_fallback
        adapter.asyncio.sleep = fake_sleep
        try:
            await instance._turn_stream_loop()
        finally:
            adapter.asyncio.sleep = original_sleep

        self.assertEqual(websocket_attempts, 2)
        self.assertEqual(fallback_attempts, 2)
        self.assertGreaterEqual(len(sleeps), 2)
        self.assertFalse(instance.marked_disconnected)

    async def test_http_503_polling_path_keeps_loop_alive(self):
        instance = self._new_adapter(prefer_websocket=False)
        http_attempts = 0
        sleeps = []

        async def refresh():
            return None

        async def fail_http_once(*, fallback_delay=None):
            nonlocal http_attempts
            http_attempts += 1
            if http_attempts >= 3:
                instance._running = False
            raise RuntimeError("HTTP 503: review restarting")

        original_sleep = adapter.asyncio.sleep

        async def fake_sleep(delay):
            sleeps.append(delay)
            await original_sleep(0)

        instance._refresh_channel_directory_if_due = refresh
        instance._http_pending_turn_once = fail_http_once
        adapter.asyncio.sleep = fake_sleep
        try:
            await instance._turn_stream_loop()
        finally:
            adapter.asyncio.sleep = original_sleep

        self.assertEqual(http_attempts, 3)
        self.assertGreaterEqual(len(sleeps), 3)
        self.assertFalse(instance.marked_disconnected)

    async def test_auth_error_during_http_fallback_stops_stream(self):
        instance = self._new_adapter(prefer_websocket=True)

        async def refresh():
            return None

        async def fail_websocket():
            raise adapter.XiaoduiyouWebSocketError("websocket closed")

        async def fail_http_with_auth(*, fallback_delay=None):
            raise adapter.XiaoduiyouAuthError("HTTP 401: UNAUTHENTICATED")

        instance._refresh_channel_directory_if_due = refresh
        instance._websocket_pending_turn_loop = fail_websocket
        instance._http_pending_turn_once = fail_http_with_auth

        await instance._turn_stream_loop()

        self.assertFalse(instance._running)
        self.assertTrue(instance.marked_disconnected)


if __name__ == "__main__":
    unittest.main()
