---
name: xiaoduiyou-codex-platform
description: Use when connecting Codex to Xiaoduiyou, claiming Xiaoduiyou Agent turns, sending progress/completions, reading or writing Growth Diary data, or working with Xiaoduiyou platform documents through the local MCP tools.
---

# Xiaoduiyou Codex Platform

Use this skill when a user asks Codex to connect to Xiaoduiyou or handle Xiaoduiyou platform work.

## Connection

The MCP server reads connection values from:

- `XDY_BASE_URL` or `XIAODUIYOU_BASE_URL`
- `XDY_CONNECTION_TOKEN` or `XIAODUIYOU_CONNECTION_TOKEN`
- `~/.codex/xiaoduiyou-connection.json`, written by `xiaoduiyou_connection_configure`

Use the values supplied by the Xiaoduiyou settings page for the active connection.

## Workflow

1. Call `xiaoduiyou_connection_status` first to verify the server has a base URL and token.
2. If status is not configured, call `xiaoduiyou_connection_configure` with the `XDY_BASE_URL` and `XDY_CONNECTION_TOKEN` from the Xiaoduiyou prompt, then call status again with `probe: true`.
3. For platform turns, call `xiaoduiyou_agent_turn_claim`.
4. To wait for new platform messages in an active Codex thread, call `xiaoduiyou_agent_turn_watch`.
5. Use `xiaoduiyou_agent_turn_progress` for visible progress.
6. Complete with `xiaoduiyou_agent_turn_complete`, including `document_actions` only when the user explicitly asked for document creation, update, or deletion.
7. Use `xiaoduiyou_agent_turn_fail` only when the turn cannot be completed.

Codex does not run a hidden background receiver after the thread goes idle. For Hermes-like background connectivity, install and start `xiaoduiyou-codex-runner`. Use `xiaoduiyou_agent_turn_watch` only for active-thread diagnosis or manual handling.

## Runtime Skill Routing

These runtime skills are installed by the `xiaoduiyou-runtime-skills` Codex plugin. If they are missing from the Codex skill list, rerun `scripts/install-codex-runner.sh` before guessing platform behavior.

- Chat-only tasks, cards, runtime messages: follow `xiaoduiyou-im`.
- Documents, content packages, process docs, publish notes: follow `xiaoduiyou-doc-content-package`.
- Growth Diary records, schema, views, and diary photos: follow `xiaoduiyou-growth-diary`.

## Growth Diary Rules

Always call `xiaoduiyou_growth_diary_get` before `xiaoduiyou_growth_diary_patch`.

For new records, `records[]` must use:

```json
{
  "table_id": "tbl_growth_events",
  "source": "agent",
  "values": {
    "title": "Milk 150ml",
    "event_type": "milk",
    "quantity": 150,
    "unit": "ml"
  }
}
```

Use `updates` for existing cells and `deletions` for deletes. Never send `values: null`.
