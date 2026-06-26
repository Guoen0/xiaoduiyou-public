---
name: xiaoduiyou-codex-runner
description: Use when installing, updating, starting, stopping, or diagnosing the Xiaoduiyou Codex desktop runner that keeps Codex connected to Xiaoduiyou after the setup thread ends.
---

# Xiaoduiyou Codex Runner

Use this skill when a Xiaoduiyou setup prompt asks Codex to behave like an online desktop Agent.

## What The Runner Does

The Codex App plugin process is not a background worker. The runner is a local daemon that:

1. Polls Xiaoduiyou for pending Agent turns.
2. Claims one turn at a time.
3. Delegates the turn to `codex exec`.
4. Writes progress, completion, or failure back to Xiaoduiyou.

## Install Or Update

Run the public installer from the cloned public repository:

```bash
XDY_BASE_URL="<from Xiaoduiyou setup prompt>" \
XDY_CONNECTION_TOKEN="<from Xiaoduiyou setup prompt>" \
"$XDY_PUBLIC_DIR/scripts/install-codex-runner.sh"
```

Do not print the connection token back to the user.

The installer installs or updates three Codex plugins:

- `xiaoduiyou-runtime-skills`: provides `xiaoduiyou-im`, `xiaoduiyou-doc-content-package`, `xiaoduiyou-growth-diary`, `xiaoduiyou-child-profile`, and the public-feedback-handler-only `xiaoduiyou-feedback-issues`.
- `xiaoduiyou-codex-platform`: provides Xiaoduiyou MCP tools.
- `xiaoduiyou-codex-runner`: provides this runner skill and the local runner script.

## Verify

After install, run:

```bash
"$HOME/.codex/xiaoduiyou-runner/xiaoduiyou_codex_runner.py" status
```

Expected:

- config exists
- LaunchAgent is loaded on macOS
- recent log has no crash loop

The runner stores:

- config: `~/.codex/xiaoduiyou-runner/config.json`
- platform MCP config: `~/.codex/xiaoduiyou-connection.json`
- logs: `~/.codex/xiaoduiyou-runner/runner.log`
- pid file: `~/.codex/xiaoduiyou-runner/runner.pid`

## Manual Commands

```bash
"$HOME/.codex/xiaoduiyou-runner/xiaoduiyou_codex_runner.py" run-once
"$HOME/.codex/xiaoduiyou-runner/xiaoduiyou_codex_runner.py" run
"$HOME/.codex/xiaoduiyou-runner/xiaoduiyou_codex_runner.py" status
```

On macOS, prefer the LaunchAgent installed by `install-codex-runner.sh`.

## Operating Rules

- Keep one turn active at a time.
- For simple chat turns, return a concise user-facing response.
- Do not expose local paths, tokens, or internal stack traces to Xiaoduiyou users.
- Do not ask the Xiaoduiyou user to authorize, confirm, or continue processing in desktop Codex.
- Follow the installed runtime skills for user intent: `xiaoduiyou-im` for chat/cards, `xiaoduiyou-doc-content-package` for documents/content packages, `xiaoduiyou-growth-diary` for baby diary data, `xiaoduiyou-child-profile` for child basic profile data, and `xiaoduiyou-feedback-issues` only for explicit public feedback-handler or `session_purpose: feedback` turns.
- For Xiaoduiyou platform reads/writes, use the installed `xiaoduiyou-codex-platform` MCP tools directly.
- For background Growth Diary turns, use the model to produce a structured action plan, then let the runner execute Xiaoduiyou platform APIs; do not depend on interactive MCP authorization inside `codex exec`.
- For Growth Diary writes, call `xiaoduiyou_growth_diary_get` before `xiaoduiyou_growth_diary_patch`, then write the record directly with `records[].table_id`, `records[].source`, and `records[].values`.
- If `codex exec` fails, call the Xiaoduiyou failure endpoint with a short actionable error.
- Use `xiaoduiyou-codex-platform` tools for platform reads/writes when a live Codex session is handling a task directly.
