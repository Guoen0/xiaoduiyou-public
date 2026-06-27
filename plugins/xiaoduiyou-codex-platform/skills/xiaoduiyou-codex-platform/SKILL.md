---
name: xiaoduiyou-codex-platform
description: Use when connecting Codex to Xiaoduiyou, claiming Xiaoduiyou Agent turns, sending progress/completions, reading or writing Growth Diary or child profile data, or working with Xiaoduiyou platform documents through the local MCP tools.
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
6. When a Codex action needs human authorization or a slash/control confirmation, create a Xiaoduiyou card with `xiaoduiyou_interactive_request_create`, then use `xiaoduiyou_interactive_request_wait` or `xiaoduiyou_interactive_request_get` before continuing.
7. Complete with `xiaoduiyou_agent_turn_complete`, including `document_actions` only when the user explicitly asked for document creation, update, or deletion.
8. Use `xiaoduiyou_agent_turn_fail` only when the turn cannot be completed.

Codex does not run a hidden background receiver after the thread goes idle. For Hermes-like background connectivity, install and start `xiaoduiyou-codex-runner`. Use `xiaoduiyou_agent_turn_watch` only for active-thread diagnosis or manual handling.

## Runtime Skill Routing

These runtime skills are installed by the `xiaoduiyou-runtime-skills` Codex plugin. If they are missing from the Codex skill list, rerun `scripts/install-codex-runner.sh` before guessing platform behavior.

- Chat-only tasks, cards, runtime messages: follow `xiaoduiyou-im`; use `xiaoduiyou_im_send` for clickable image cards.
- Documents, content packages, process docs, publish notes: follow `xiaoduiyou-doc-content-package`.
- Growth Diary records, schema, views, and diary photos: follow `xiaoduiyou-growth-diary`.
- Child profile and development fields such as name, birthday, gender, allergy, height, weight, photo, four development dimensions, or skill-node states: follow `xiaoduiyou-child-profile`.
- Public feedback-handler or explicit `session_purpose: feedback` turns: follow `xiaoduiyou-feedback-issues`; ordinary chat that mentions feedback stays in `xiaoduiyou-im`.

## Child Profile Rules

Always call `xiaoduiyou_child_get` before `xiaoduiyou_child_patch`.

Patch only fields the user explicitly provided under `profile`: `name`, `birthday`, `gender`, `allergy`, `heightCm`, `weightKg`, or `photoUrl`.

For development progress, call `xiaoduiyou_child_get` and read `development[].nodes[]`. Patch `skill_node_states` with exact returned node keys and boolean values only. Do not invent node keys or overwrite unrelated nodes.

## Growth Diary Rules

Always call `xiaoduiyou_growth_diary_get` before `xiaoduiyou_growth_diary_patch`.

For Agent-created records, `date` is required as `YYYY-MM-DD` and `occurred_at` is required as `YYYY-MM-DD HH:mm:ss` with the same date. Time-only values like `19:20` are invalid and will be rejected by the API.

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

## IM Cards

For Xiaoduiyou chat visual cards, call `xiaoduiyou_im_send` instead of uploading images yourself. The tool accepts OpenAI Responses-style `content[]` parts:

```json
{
  "channel": "default",
  "content": [
    { "type": "input_text", "text": "点图片可以打开来源。" },
    {
      "type": "input_image",
      "image_url": "data:image/png;base64,...",
      "detail": "auto",
      "display": {
        "title": "卡片标题",
        "subtitle": "来源或说明",
        "badge": "参考",
        "link_url": "https://example.com/source"
      }
    }
  ]
}
```

Never pass local paths, `file:`, `blob:`, `localhost`, or private-network URLs.

## Authorization Cards

For human approval inside Xiaoduiyou, use the interactive request tools instead of plain text:

```json
{
  "session_id": "<active session_id from the claimed turn>",
  "turn_id": "<active turn_id from the claimed turn>",
  "kind": "exec_approval",
  "title": "需要授权执行命令",
  "message": "Codex 请求执行命令，需要授权后继续。",
  "command": "npm run deploy:review",
  "reason": "部署到 review 环境",
  "actions": ["once", "session", "always", "deny"],
  "timeout_seconds": 300
}
```

After creating the card, wait for the user's choice. Treat `deny`, `cancel`, and `expired` as a stop for that protected action.
