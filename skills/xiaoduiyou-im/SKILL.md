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

1. Visual cards in Xiaoduiyou are `image_attachments[]`, not `MEDIA:/...`, Markdown images, browser screenshots, or link-only text.
2. Local/server-static paths are invalid in final chat cards. Upload images to `/api/assets` first.
3. Verify delivery: response event type, attachment count, and at least one image URL HTTP 200 image content-type.
4. For product questions: Xiaohongshu provides lived-experience/reference evidence; Taobao/Tmall provides buyable candidates/parameters.
5. For document/content-package artifacts, travel plans, publish tabs, or process docs, load `xiaoduiyou-doc-content-package`; do not keep that workflow inside IM.
6. For Growth Diary records, load `xiaoduiyou-growth-diary`; do not send diary-only data as generic chat cards unless the user asks for a chat preview.

## Case map owned by IM

| User says / situation | Open/use | Why |
|---|---|---|
| `给我视觉卡片` / `卡片` / `点图片打开` | `references/visual-card-delivery.md` + `scripts/send_visual_cards.py` | Chat visual cards are `image_attachments`; the script sends them. |
| `淘宝上找一下...给我` / `淘宝上找一下...给我卡片` | `references/product-question-workflow.md` then `references/visual-card-delivery.md` | Product research plus clickable candidate cards. |
| `小红书找参考帖` / source examples | `references/product-question-workflow.md` and `references/visual-card-delivery.md` | Source/reference cards and links. |
| Runtime send/message/card payload details | `references/runtime-api-reference.md` | Chat message endpoint and `image_attachments` payloads. |
| Asset upload/image URL verification for chat cards | `references/image-upload-contract.md` | Upload local/generated images before final UI use. |
| Runtime turn lifecycle / message stream state | `references/runtime-turn-lifecycle.md` | Debug or reason about Agent 对话页 runtime turns. |

## First-pass routing

| User intent in Agent 对话页 | Route |
|---|---|
| Visual/clickable image cards | handle here; open `references/visual-card-delivery.md` |
| Product questions: XHS + Taobao/Tmall + cards | handle here; open `references/product-question-workflow.md` |
| Runtime endpoints and message payloads | handle here; open `references/runtime-api-reference.md` |
| Upload/verify images | handle here; open `references/image-upload-contract.md` |
| Document/content-package artifacts, travel plans, publish tabs, process docs | load `xiaoduiyou-doc-content-package` |
| 成长日记 / diary records / diary photos | load `xiaoduiyou-growth-diary` |

## Scripts

- `scripts/send_visual_cards.py`: upload local/remote images to Xiaoduiyou assets and send structured `image_attachments` to a session.

Quick use:

```bash
python ~/.hermes/skills/productivity/xiaoduiyou-im/scripts/send_visual_cards.py --list-sessions
python ~/.hermes/skills/productivity/xiaoduiyou-im/scripts/send_visual_cards.py \
  --session-id sess_0053 \
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
