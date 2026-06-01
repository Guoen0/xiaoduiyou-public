# Xiaoduiyou runtime API quick reference

This is the compact interface reference for connected usage Agents. Use the Xiaoduiyou origin/auth context provided by the active runtime prompt/turn (`runtime_context.base_url` when present). Do not invent credentials, call private developer-only endpoints, use maintainer-specific URLs, or switch to a different Xiaoduiyou origin from local config or an unrelated browser tab.

## Turn lifecycle

### Poll pending turn

`GET /api/hermes/turns/pending`

- `200`: a turn payload is available. Use the returned `turn_id`, user message/context, session/document identifiers, and any auth/session metadata supplied by the runtime.
- `404 {"error":"NO_PENDING_TURN"}`: healthy idle state; do not treat as failure.

### Send progress / tool progress

`POST /api/hermes/turns/{turn_id}/events`

Common payload:

```json
{
  "label": "小队友",
  "detail": "正在抓取小红书参考帖和淘宝候选…"
}
```

The progress payload may include richer UI fields:

```json
{
  "label": "小队友",
  "detail": "点图片可以打开来源。",
  "image_urls": ["https://durable-image.example.com/a.webp"],
  "image_attachments": [
    {
      "image_url": "https://durable-image.example.com/card.webp",
      "link_url": "https://www.xiaohongshu.com/explore/xxxx",
      "title": "参考帖标题",
      "subtitle": "小红书 · 为什么相关",
      "badge": "参考帖"
    }
  ],
  "artifact_link": {
    "artifact_id": "artifact_xxx",
    "label": "过程文档",
    "title": "产品调研过程"
  }
}
```

`image_attachments[]` fields:

- `image_url` required; durable browser-accessible image URL only.
- `link_url` optional but preferred for source/product click-through.
- `title`, `subtitle`, `badge` optional display metadata.

### Send a normal outbound chat message

Use this when a connected Agent needs to send a message to an existing Xiaoduiyou session outside an active pending turn, for example a scheduled/initiated message or a platform `send_message` call.

`POST /api/agent/sessions/{session_id}/messages`

Headers are the same Agent auth headers as turn polling/callbacks. Minimal body:

```json
{
  "text": "这是要发到小队友会话里的正文。\n小红书：https://www.xiaohongshu.com/explore/xxxx\n淘宝：https://item.taobao.com/item.htm?id=123456"
}
```

Compatibility notes:

- Plain `http://` / `https://` URLs in `text` auto-render as clickable links in the chat bubble.
- Xiaohongshu URLs are sanitized client-side for `xsec_*` query parameters when rendered.
- Taobao/Tmall links work as normal clickable URLs; prefer canonical `https://item.taobao.com/item.htm?id=...` or `https://detail.tmall.com/item.htm?id=...`.
- The endpoint also accepts official-case-style visual cards through `image_attachments`. Use durable uploaded image URLs only:

```json
{
  "text": "我把小红书参考和淘宝候选放在下面，点图片可以打开来源。",
  "image_attachments": [
    {
      "image_url": "https://xiaoduiyou-assets.example.com/xhs-cover.webp",
      "link_url": "https://www.xiaohongshu.com/explore/xxxx",
      "title": "真实使用参考",
      "subtitle": "小红书 · 同场景经验",
      "badge": "参考帖"
    },
    {
      "image_url": "https://xiaoduiyou-assets.example.com/taobao-item.webp",
      "link_url": "https://item.taobao.com/item.htm?id=123456",
      "title": "商品名 / 关键型号",
      "subtitle": "淘宝 · 可买候选",
      "badge": "商品候选"
    }
  ]
}
```

- Hermes/OpenClaw platform `send_message` / outbound text tools may only expose a text field. In that case send the same object as a JSON string; the Xiaoduiyou plugin/connector will parse it and POST the structured payload. This is the fastest path when the user asks to convert an existing answer into visual cards in the current chat.
- If direct `POST /api/assets` returns `UNAUTHENTICATED` because the agent is outside an active Xiaoduiyou runtime/auth context, do not stall. Prefer the platform `send_message` JSON-string path for chat-only visual cards, clearly using already obtained image URLs. Only claim durable Xiaoduiyou asset upload when `/api/assets` returned and the URL was verified.
- This session-message endpoint is for chat bubbles and visual cards. It still does **not** mutate `artifact` or run `document_actions`; use active-turn `events` / `callback` plus document tools for artifacts and document mutations.

### Complete turn

`POST /api/hermes/turns/{turn_id}/callback`

Include a user-facing final `progress`/message plus either:

- `artifact` for generated/revised content packages; or
- `document_actions` for document/process-only operations.

Generic content artifact:

```json
{
  "progress": "已整理好结果。",
  "artifact": {
    "schema": "xdy.artifact_blocks.v1",
    "artifact_id": "artifact_xxx",
    "version_id": "version_xxx",
    "blocks": {
      "title": "标题",
      "body": "正文",
      "source_markdown": "## 过程材料\n...",
      "ui_templates": ["xiaohongshu"],
      "publish_notes": {
        "xiaohongshu": {
          "platform": "xiaohongshu",
          "label": "小红书发布稿",
          "title": "发布标题",
          "body": "发布正文",
          "images": ["https://durable-image.example.com/cover.webp"],
          "hashtags": ["#话题"]
        }
      }
    }
  }
}
```

## Assets

`POST /api/assets`

Multipart fields:

- `file`: required file upload.
- `source`: use `agent_generated` for generated Agent output; use a source-specific value such as `xhs_reference` or `taobao_reference` only if the runtime supports it. If unsure, keep `agent_generated` and record provenance in metadata/process notes.
- `session_id` / `document_id`: include when available.

Read the response URL:

- prefer top-level `url`;
- otherwise use `asset.public_url`.

Always verify rendered image URLs with `GET` or `HEAD`: HTTP `200` and `content-type` starts with `image/`.

## Document actions/tools

When the runtime exposes Xiaoduiyou document tools, use them instead of direct database writes:

- `xiaoduiyou_documents_create(title, body?, block_json?, ui_templates?, fields?, attach_to_session?)`
- `xiaoduiyou_documents_update(document_id?, command?, title?, body?, block_json?, ui_templates?, fields?, blocks?)`
- `xiaoduiyou_documents_delete(document_id?)`

Supported update commands:

- `overwrite`: replace title/body/block_json/templates/fields as supplied.
- `append_blocks`: append structured blocks.
- `patch_fields`: update metadata fields and/or `ui_templates` without rewriting the whole document.

Use `fields.ui_templates` / top-level `ui_templates` and `fields.publish_notes` for visible result tabs. Use `body`, `block_json`, and `fields.source_markdown` for process/evidence material.

## Growth diary

For 成长日记 tasks only:

- `GET /api/growth-diary` before writing, so enum options and live schema are current.
- `PATCH /api/growth-diary` for records, updates, deletions, field options, and view changes.
- Upload photos via `/api/assets` before writing attachment/image fields.

Do not model diary records as content-package `publish_notes`.

## Failure boundary

If a tool/source/API fails:

- Send a concise progress/failure event naming what failed and what still succeeded.
- Never fabricate source links, prices, images, or published state.
- If final output is partial, label assumptions and missing checks explicitly.
