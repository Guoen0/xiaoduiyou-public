# Xiaoduiyou Hermes Platform Plugin

This plugin connects Xiaoduiyou to Hermes Agent as a Gateway platform adapter.

Mental model:

```text
Xiaoduiyou UI
  → pending Hermes turn in Xiaoduiyou
  → XiaoduiyouAdapter polls /api/hermes/turns/pending
  → Hermes Gateway turns it into MessageEvent
  → Hermes Agent runs the task
  → XiaoduiyouAdapter sends progress/final callbacks
  → Xiaoduiyou event log + WebSocket update
```

Install or update this plugin and the Xiaoduiyou runtime skills by running the public repository installer directly. Do not manually `rsync` this plugin or write a multi-step update plan unless you are debugging the installer itself:

```bash
XDY_PUBLIC_REPO="https://github.com/Guoen0/xiaoduiyou-public.git"
XDY_PUBLIC_DIR="$HOME/.xiaoduiyou/xiaoduiyou-public"
mkdir -p "$HOME/.xiaoduiyou"
if [ -d "$XDY_PUBLIC_DIR/.git" ]; then
  git -C "$XDY_PUBLIC_DIR" fetch origin main
  git -C "$XDY_PUBLIC_DIR" reset --hard origin/main
  git -C "$XDY_PUBLIC_DIR" clean -fd
else
  git clone "$XDY_PUBLIC_REPO" "$XDY_PUBLIC_DIR"
fi

"$XDY_PUBLIC_DIR/scripts/install-hermes.sh"
```

The installer preserves existing `${HERMES_HOME:-~/.hermes}/config.yaml` Xiaoduiyou `base_url` and `connection_token` when they are already configured, installs the platform plugin and runtime skills into the active Hermes home, and restarts the gateway. See the root `README.md` for the full Agent setup prompt.

Do not configure `platform_toolsets.xiaoduiyou` as only `["xiaoduiyou"]`: that exposes Xiaoduiyou document tools but removes normal Hermes local tools such as file, terminal, web search, browser, and code execution.

## Current boundary

- Text replies are supported.
- Agent-facing messages include real sender identity and compact current-screen context when Xiaoduiyou provides `screen_context`, so vague replies like “这个” can be resolved without polluting the visible user bubble.
- Hermes pairing and connection identity are scoped to the connected Xiaoduiyou Home, not to each family member sender. The real member identity is still included in the Agent-facing message and `agent_runtime_context.sender`.
- Xiaoduiyou interaction targets are channels. The stable Home target is `xiaoduiyou:主对话` / `xiaoduiyou:default`; named sidebar channels should appear by their visible title, and family channels should be marked as `group`.
- Scheduled Xiaoduiyou messages must use cron `deliver` targets such as `xiaoduiyou:主对话` or `xiaoduiyou:<频道名>`. Do not schedule a future prompt that calls `send_message`.
- Document tools are available for explicit document create/update/delete requests.
- `pending turn`, `callback`, and `event_log` are implementation details; the UI should feel like direct chat with Hermes.
