# Xiaoduiyou Hermes Plugin

This is the maintained Hermes Gateway platform plugin for Xiaoduiyou. Install it instead of asking an Agent to implement Xiaoduiyou polling/callback logic by itself.

## What it provides

- Hermes platform: `xiaoduiyou`
- WebSocket streaming of Xiaoduiyou pending turns, with HTTP pending-poll fallback for older Xiaoduiyou backends
- Progress/tool-progress delivery to Xiaoduiyou events
- Final callback delivery to Xiaoduiyou
- Agent-facing sender identity and current-screen context headers for vague messages such as “把这个改短一点”
- Channel-directory compatibility for Xiaoduiyou targets: Hermes should list `xiaoduiyou:主对话` and current sidebar channel names, with family channels marked as `group`, even on Hermes versions that only read `channel_directory.json`
- Cron delivery support through `deliver="xiaoduiyou:<channel name>"`; cron jobs must not schedule a future `send_message` call
- Xiaoduiyou document tools registered in toolset `xiaoduiyou`

## Hermes install layout

Recommended installation path:

```text
${HERMES_HOME:-~/.hermes}/plugins/xiaoduiyou_hermes_platform/
  plugin.yaml
  adapter.py
  __init__.py
```

## Config

Enable the plugin and platform in `${HERMES_HOME:-~/.hermes}/config.yaml`. If you run Hermes under a named profile, set `HERMES_HOME` to that profile directory before installing:

```yaml
plugins:
  enabled:
    - xiaoduiyou-hermes-platform

platforms:
  xiaoduiyou:
    enabled: true
    extra:
      base_url: https://YOUR_XIAODUIYOU_ORIGIN
      prefer_websocket: true
      poll_interval_seconds: 1.0
      websocket_ping_interval_seconds: 25.0
      websocket_ping_timeout_seconds: 10.0
    home_channel:
      platform: xiaoduiyou
      chat_id: xiaoduiyou
      name: 主对话

platform_toolsets:
  xiaoduiyou:
    - web
    - browser
    - terminal
    - file
    - code_execution
    - vision
    - image_gen
    - tts
    - skills
    - todo
    - memory
    - session_search
    - clarify
    - delegation
    - cronjob
    - messaging
    - xiaoduiyou
```

Do not configure `platform_toolsets.xiaoduiyou` as only `[xiaoduiyou]`: that exposes Xiaoduiyou document tools but removes normal Hermes local tools such as file, terminal, web search, browser, and code execution.

Use `platforms.xiaoduiyou.extra.base_url` and `platforms.xiaoduiyou.extra.connection_token` as the source of truth. Avoid setting `XIAODUIYOU_BASE_URL` or `XIAODUIYOU_CONNECTION_TOKEN` in the gateway environment because those variables override `config.yaml` and can leave Hermes connected to an old Xiaoduiyou environment.

The plugin probes `/api/hermes/health` during startup and reconnects, then connects to `/ws/hermes/turns/pending` by default. If the Xiaoduiyou backend is older and does not expose the health endpoint yet, the plugin falls back to the existing pending-turn stream. Exec approval / slash confirmation cards still use `/ws/hermes/interactive-requests/:request_id`. WebSocket connections send protocol-level keepalive pings every 25 seconds by default and reconnect when the server does not answer within 10 seconds. `poll_interval_seconds` is retained as the fallback/retry cadence when WebSocket is unavailable or disabled with `prefer_websocket: false`; `probe_health: false` is reserved for temporary emergency bypasses.

Restart Hermes Gateway after installing or changing config:

```bash
hermes gateway restart
```

After restart, verify channel discovery from Hermes:

```text
send_message(action="list")
```

The list should include `xiaoduiyou:主对话` and named Xiaoduiyou channels such as `xiaoduiyou:达拉崩吧`. If these channels are missing, rerun the Xiaoduiyou install/update prompt and restart the corresponding Hermes profile.

## Important boundary

The plugin owns the Xiaoduiyou connection protocol. The Agent should load `xiaoduiyou-im`, `xiaoduiyou-doc-content-package`, or `xiaoduiyou-growth-diary` for runtime behavior; it should not write its own Xiaoduiyou connector or manually poll/callback unless it is debugging the maintained plugin.
