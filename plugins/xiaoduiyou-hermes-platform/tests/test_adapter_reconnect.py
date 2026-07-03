from __future__ import annotations

import importlib.util
import os
import sys
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

        self.assertEqual(calls, ["https://review.example.test/api/hermes/health", "websocket"])
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

        self.assertEqual(calls, ["https://review.example.test/api/hermes/health", "websocket"])
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
