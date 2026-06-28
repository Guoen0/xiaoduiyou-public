# Xiaoduiyou runtime turn lifecycle

Use this when a connected Agent needs to poll Xiaoduiyou work, send progress, and complete a turn. This is runtime usage only; do not change Xiaoduiyou source code, deployment, database, or connector configuration from this public skill.

## Core boundary

A connected usage Agent may:

- read the user's Xiaoduiyou turn/task context;
- send progress/tool-progress events;
- complete a turn with an `xdy.artifact_blocks.v1` content package;
- create/update/delete process documents only through Xiaoduiyou document actions/tools;
- upload local/generated images through Xiaoduiyou's asset API before referencing them;
- operate 成长日记 through `/api/growth-diary` when the task is a diary/logging task.

A connected usage Agent must not:

- modify Xiaoduiyou website source code, UI, CSS, API implementation, deployment, SQLite/runtime data, or Hermes/Xiaoduiyou configuration;
- claim that it changed the website itself;
- expose credentials, API keys, tokens, TOS/OSS secrets, or connection strings. Redact any accidental secret-like source text as `[REDACTED]`.

## Turn lifecycle endpoints

Use the Xiaoduiyou origin and auth context supplied by the active connection prompt/runtime context.

1. Poll pending work:
   - `GET /api/hermes/turns/pending`
   - `200 {"turn": null}` means healthy idle state.
2. Send incremental progress:
   - `POST /api/hermes/turns/{turn_id}/events`
   - body may include `progress` or `tool_progress`.
3. Complete the turn:
   - `POST /api/hermes/turns/{turn_id}/callback`
   - include a user-facing `progress` message and either:
     - `artifact` for generated/revised content packages, or
     - `document_actions` for document/process-draft-only operations.

For platform-originated outbound messages without an active pending turn, send a chat message to the stable Home channel (`default`, shown to users as `主对话`):

- `POST /api/agent/im/send`
- default/Home body: `{ "channel": "default", "text": "正文，可包含 https://www.xiaohongshu.com/explore/... 或 https://item.taobao.com/item.htm?id=..." }`
- visual-card body: `{ "channel": "default", "content": [{ "type": "input_text", "text": "点图片可以打开来源。" }, { "type": "input_image", "image_url": "https://durable-asset/card.webp", "display": { "link_url": "https://www.xiaohongshu.com/explore/...", "title": "参考帖标题", "subtitle": "小红书 · 经验参考", "badge": "参考帖" } }] }`
- Use `session_id` only when intentionally targeting one existing Xiaoduiyou session.
- Links in `text` render clickable. `image_attachments[].link_url` makes the card image/title clickable. Use this for official-case-style Xiaohongshu/Taobao visual cards. For artifacts and document mutations, keep using active-turn `events`/`callback` plus document tools.

For scheduled fixed-text outbound messages, create a no-agent script cron with a `deliver` target such as `xiaoduiyou:default`, `xiaoduiyou:主对话`, or `xiaoduiyou:<visible channel title>`. The script must print only the exact user-facing reply. Do not schedule a future `send_message` call; cron runs do not expose the messaging toolset, and delivery success is determined by the scheduler/platform response.

Before final callback, validate that publish tabs contain only user-facing deliverables, sources remain in `过程材料`, and every image URL is browser-accessible.

## When the user asks for product/UI changes

Say clearly that this connected usage Agent can update content artifacts/documents and growth-diary records through runtime APIs, but website/product changes must be handled through Xiaoduiyou development/maintenance. Do not pretend to edit Xiaoduiyou source code or deploy the site from this usage workflow.

## Final callback checklist

- The user-facing final message states the actual outcome, not internal steps.
- If returning a content package, `ui_templates` selects only templates the user/Agent wants rendered.
- Each selected template has matching `publish_notes.<template>` result data.
- Publish tabs contain final copy/images only, not process notes, prompts, references, or research dumps.
- Every local/generated image has been uploaded through `/api/assets` and URL-verified.
- `source_markdown` / process document preserves enough source, references, visual direction, and decisions for later QA.
- No credentials or secrets are present in final artifact/document text.
