---
name: xiaoduiyou-im
description: "Primary entrypoint for Xiaoduiyou Agent chat/IM intents and immediately actionable chat features: visual cards, clickable image_attachments, product/source cards, Taobao/Xiaohongshu candidate finding, asset uploads, runtime messages, and chat-only delivery. Use first when the current source/screen is Xiaoduiyou Agent 对话页."
---

# Xiaoduiyou IM

This skill is the first stop for Xiaoduiyou Agent chat-box intent. It owns chat-only delivery and all cases that can be answered inside the conversation UI without creating a document or writing Growth Diary records.

## Trigger

Load this when:

- Current session/source is Xiaoduiyou or the screen is `Agent 对话页`.
- The user asks for visual cards, product/source cards, clickable images, Xiaoduiyou message delivery, or chat result UI.
- Keywords handled here: `视觉卡片`, `卡片`, `点图`, `点图片打开`, `商品候选`, `参考帖`, `淘宝`, `小红书`, `找一下`, `给我几个`, `候选`.
- If the user asks for `旅游规划`, `旅行规划`, itinerary/travel result UI, `内容包`, `文档产物`, `发布稿`, `ui_templates`, or publish tabs, load `xiaoduiyou-doc-content-package` instead.
- If the user asks for `成长日记`, baby diary records, or diary photos/schema/views, load `xiaoduiyou-growth-diary` instead.

## Non-negotiables

1. Prefer the `xiaoduiyou_im_send` tool for visual cards. It accepts OpenAI Responses-style `content[]` parts and the Xiaoduiyou backend uploads images/assets.
2. Visual cards in Xiaoduiyou render as `image_attachments[]`, not `MEDIA:/...`, Markdown images, browser screenshots, or link-only text.
3. Local/server-static paths are invalid in final chat cards. Pass HTTPS images or `data:image/...;base64,...` to `xiaoduiyou_im_send`; never pass `/tmp`, `/Users`, `file:`, `blob:`, `localhost`, or private-network URLs.
4. Verify delivery: response event type, attachment count, and at least one image URL HTTP 200 image content-type.
5. For product questions: Xiaohongshu provides lived-experience/reference evidence; Taobao/Tmall provides buyable candidates/parameters.
6. For document/content-package artifacts, travel plans, publish tabs, or process docs, load `xiaoduiyou-doc-content-package`; do not keep that workflow inside IM.
7. For Growth Diary records, load `xiaoduiyou-growth-diary`; do not send diary-only data as generic chat cards unless the user asks for a chat preview.

## Case map owned by IM

| User says / situation | Open/use | Why |
|---|---|---|
| `给我视觉卡片` / `卡片` / `点图片打开` | `xiaoduiyou_im_send` + `references/visual-card-delivery.md` | Backend assetizes images and sends clickable `image_attachments`. |
| `淘宝上找一下...给我` / `淘宝上找一下...给我卡片` | `references/product-question-workflow.md` then `references/visual-card-delivery.md` | Product research plus clickable candidate cards. |
| `小红书找参考帖` / source examples | `references/product-question-workflow.md` and `references/visual-card-delivery.md` | Source/reference cards and links. |
| Runtime send/message/card payload details | `references/runtime-api-reference.md` | Chat message endpoint and `image_attachments` payloads. |
| Asset upload/image URL verification for chat cards | `references/image-upload-contract.md` | Upload local/generated images before final UI use. |
| Runtime turn lifecycle / message stream state | `references/runtime-turn-lifecycle.md` | Debug or reason about Agent 对话页 runtime turns. |
| Scheduled Xiaoduiyou message / reminder / cron delivery | `cronjob(action="create")` with `deliver` | Cron runs without `send_message`; delivery target must be encoded in `deliver`. |

## First-pass routing

| User intent in Agent 对话页 | Route |
|---|---|
| Visual/clickable image cards | handle here; open `references/visual-card-delivery.md` |
| Product questions: XHS + Taobao/Tmall + cards | handle here; open `references/product-question-workflow.md` |
| Runtime endpoints and message payloads | handle here; open `references/runtime-api-reference.md` |
| Upload/verify images | handle here; open `references/image-upload-contract.md` |
| Scheduled message/reminder to a Xiaoduiyou channel | use `cronjob(action="create")` with `deliver`; do not schedule a future `send_message` call |
| Document/content-package artifacts, travel plans, publish tabs, process docs | load `xiaoduiyou-doc-content-package` |
| 成长日记 / diary records / diary photos | load `xiaoduiyou-growth-diary` |

## Preferred Tool

Call `xiaoduiyou_im_send` with OpenAI Responses-style content parts. Omit `session_id` for background/default delivery; Xiaoduiyou will route it to the stable Home `default` channel, shown to users as `主对话`. Pass `session_id` only when replying to a specific active session.

```json
{
  "channel": "default",
  "content": [
    { "type": "input_text", "text": "点图片可以打开来源。" },
    {
      "type": "input_image",
      "image_url": "https://example.com/card.webp",
      "detail": "auto",
      "display": {
        "title": "龙柳鲜枝水培款",
        "subtitle": "淘宝 · 插瓶水培 · 1.2-1.5m 优先",
        "badge": "商品候选",
        "link_url": "https://s.taobao.com/search?q=..."
      }
    }
  ]
}
```

Use `data:image/png;base64,...` for generated images when you do not already have an HTTPS URL.

## Scheduled Messages

When the user asks to send a Xiaoduiyou message later, create a cron job whose delivery target is in `deliver`. Do not write a future prompt that calls `send_message`, because cron runs do not expose the messaging toolset.

For fixed-text reminders, prefer a no-agent cron script so the scheduler delivers the exact text without a future LLM turn. Create a small script under `${HERMES_HOME:-$HOME/.hermes}/scripts/`, then call `cronjob(action="create", script="<name>", no_agent=true, deliver="xiaoduiyou:<channel>")`. The script must print only the user-facing message. Do not print “已发送”, “done”, or delivery status; delivery success comes from the scheduler/platform response, not from the script text.

- Current/default Home channel: `deliver: "xiaoduiyou:default"` or `deliver: "xiaoduiyou:主对话"`.
- Named sidebar channel: `deliver: "xiaoduiyou:<visible channel title>"`, for example `xiaoduiyou:达拉崩吧`.
- If a job is LLM-driven, keep the cron prompt to the exact user-facing content, for example `请只回复：测试 cron：1 分钟到了。`.
- After creating the job, inspect the returned job object and confirm `deliver` is the intended Xiaoduiyou target, not `local`.

Example:

```json
{
  "action": "create",
  "schedule": "1m",
  "script": "xiaoduiyou-reminder-20260611-0209.sh",
  "no_agent": true,
  "deliver": "xiaoduiyou:达拉崩吧"
}
```

Script content:

```bash
#!/usr/bin/env bash
printf '%s\n' '测试 cron：1 分钟到了。'
```

## Legacy Script

- `scripts/send_visual_cards.py`: fallback for old connectors without `xiaoduiyou_im_send`; sends structured content parts through `/api/agent/im/send`, defaulting to the Home `default` channel (`主对话`).

Quick use:

```bash
HERMES_SKILL_HOME="${HERMES_HOME:-$HOME/.hermes}"
python "$HERMES_SKILL_HOME/skills/xiaoduiyou/xiaoduiyou-im/scripts/send_visual_cards.py" --list-channels
python "$HERMES_SKILL_HOME/skills/xiaoduiyou/xiaoduiyou-im/scripts/send_visual_cards.py" \
  --channel default \
  --text '点图片可以打开来源。' \
  --cards-json /tmp/cards.json
```

## Card JSON shape

```json
[
  {
    "image_path": "/tmp/card.png",
    "title": "龙柳鲜枝水培款",
    "subtitle": "淘宝 · 插瓶水培 · 1.2–1.5m 优先",
    "badge": "商品候选",
    "link_url": "https://s.taobao.com/search?q=..."
  }
]
```
