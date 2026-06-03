# Xiaoduiyou Codex Platform

Local Codex plugin that connects Codex to Xiaoduiyou through MCP tools.

## Configuration

Set the connection values provided by the Xiaoduiyou settings page before starting Codex:

```bash
export XDY_BASE_URL="https://your-xiaoduiyou-origin"
export XDY_CONNECTION_TOKEN="your-connection-token"
```

The server also accepts `XIAODUIYOU_BASE_URL` and `XIAODUIYOU_CONNECTION_TOKEN`.

## Tools

- `xiaoduiyou_connection_status`
- `xiaoduiyou_agent_turn_claim`
- `xiaoduiyou_agent_turn_progress`
- `xiaoduiyou_agent_turn_complete`
- `xiaoduiyou_agent_turn_fail`
- `xiaoduiyou_agent_sessions_list`
- `xiaoduiyou_agent_session_message`
- `xiaoduiyou_growth_diary_get`
- `xiaoduiyou_growth_diary_patch`
- `xiaoduiyou_documents_get`
- `xiaoduiyou_documents_create`
- `xiaoduiyou_documents_update`
- `xiaoduiyou_documents_delete`
- `xiaoduiyou_documents_export`

## Notes

Use the Xiaoduiyou app-provided connection values for the active connection. Do not modify the Xiaoduiyou app source when using this plugin to handle user turns or platform data.
