# Xiaoduiyou Codex Platform

Local Codex plugin that connects Codex to Xiaoduiyou through MCP tools.

## Configuration

Set the connection values provided by the Xiaoduiyou settings page before starting Codex:

```bash
export XDY_BASE_URL="https://your-xiaoduiyou-origin"
export XDY_CONNECTION_TOKEN="your-connection-token"
```

The server also accepts `XIAODUIYOU_BASE_URL` and `XIAODUIYOU_CONNECTION_TOKEN`.

If Codex was already running and the MCP process did not inherit those environment variables,
call `xiaoduiyou_connection_configure` once with the Xiaoduiyou settings-page values. The plugin
stores them in `~/.codex/xiaoduiyou-connection.json`.

## Tools

- `xiaoduiyou_connection_status`
- `xiaoduiyou_connection_configure`
- `xiaoduiyou_agent_turn_claim`
- `xiaoduiyou_agent_turn_watch`
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

Codex does not run a hidden background receiver after a thread becomes idle. Keep a Xiaoduiyou
Codex thread active by calling `xiaoduiyou_agent_turn_watch`, then complete each claimed turn before
watching for the next one.
