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

Use the values supplied by the Xiaoduiyou settings page for the active connection.

## Workflow

1. Call `xiaoduiyou_connection_status` first to verify the server has a base URL and token.
2. For platform turns, call `xiaoduiyou_agent_turn_claim`.
3. Use `xiaoduiyou_agent_turn_progress` for visible progress.
4. Complete with `xiaoduiyou_agent_turn_complete`, including `document_actions` only when the user explicitly asked for document creation, update, or deletion.
5. Use `xiaoduiyou_agent_turn_fail` only when the turn cannot be completed.

## Runtime Skill Routing

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
