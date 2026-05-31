# Xiaoduiyou Hermes Plugin

This is the maintained Hermes Gateway platform plugin for Xiaoduiyou. Install it instead of asking an Agent to implement Xiaoduiyou polling/callback logic by itself.

## What it provides

- Hermes platform: `xiaoduiyou`
- Polling of Xiaoduiyou pending turns
- Progress/tool-progress delivery to Xiaoduiyou events
- Final callback delivery to Xiaoduiyou
- Agent-facing sender identity and current-screen context headers for vague messages such as “把这个改短一点”
- Xiaoduiyou document tools registered in toolset `xiaoduiyou`

## Hermes install layout

Recommended installation path:

```text
~/.hermes/plugins/xiaoduiyou_platform/
  plugin.yaml
  adapter.py
  __init__.py
```

## Config

Enable the plugin and platform in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - xiaoduiyou-platform

platforms:
  xiaoduiyou:
    enabled: true
    extra:
      base_url: https://YOUR_XIAODUIYOU_ORIGIN
      poll_interval_seconds: 1.0
    home_channel:
      platform: xiaoduiyou
      chat_id: xiaoduiyou
      name: Xiaoduiyou

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

Alternatively set `XIAODUIYOU_BASE_URL=https://YOUR_XIAODUIYOU_ORIGIN` in the gateway environment.

Restart Hermes Gateway after installing or changing config:

```bash
hermes gateway restart
```

## Important boundary

The plugin owns the Xiaoduiyou connection protocol. The Agent should load `xiaoduiyou-usage-workflow` for content-package rules, but it should not write its own Xiaoduiyou connector or manually poll/callback unless it is debugging the maintained plugin.
