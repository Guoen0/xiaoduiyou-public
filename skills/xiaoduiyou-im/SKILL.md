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
- If the user asks to view or update child basic info or development progress such as baby name/nickname, birthday, gender, allergy, height, weight, child photo, four development dimensions, skill nodes, 点亮/熄灭, or 已掌握/未掌握, load `xiaoduiyou-child-profile` instead.
- If runtime/session context explicitly has `session_purpose: feedback`, or the current Hermes profile is the configured Xiaoduiyou public feedback handler, load `xiaoduiyou-feedback-issues` instead. Do not route ordinary chat just because the user says `反馈`, `bug`, `问题`, or `issue`.
- If the user asks for baby/toddler psychology, behavior, routines, feeding cooperation, sleep/meal cooperation, discipline, emotion coaching, attachment, autonomy, play, or family caregiving decisions without asking to write diary data, answer in chat here.

## Non-negotiables

0. Xiaoduiyou operating knowledge belongs in Xiaoduiyou skills, not Hermes memory. Treat the agent as a Xiaoduiyou developer and earliest user: when a Xiaoduiyou workflow lesson, UI/runtime convention, or caregiver shorthand is discovered, patch the relevant `xiaoduiyou-*` skill so other agents can inherit it; do not store that experience only in profile memory.
1. **If the current screen/source is Xiaoduiyou Agent 对话页 and the user asks to generate or return an image, load this skill before final delivery even if the creative prompt itself is handled by an image-generation skill.** The deliverable must be a Xiaoduiyou IM image/card, not a generic Hermes Markdown image.
2. Prefer the `xiaoduiyou_im_send` tool for visual cards. It accepts OpenAI Responses-style `content[]` parts and the Xiaoduiyou backend uploads images/assets.
3. Visual cards in Xiaoduiyou render as `image_attachments[]`, not `MEDIA:/...`, Markdown images, browser screenshots, or link-only text.
4. Local/server-static paths are invalid in final chat cards. Pass HTTPS images or `data:image/...;base64,...` to `xiaoduiyou_im_send`; never pass `/tmp`, `/Users`, `file:`, `blob:`, `localhost`, or private-network URLs.
5. **Send the Xiaoduiyou IM payload inside the same active turn before the final text reply.** Do not first finalize with a local/Markdown path and try to "补发" later; the runtime may close the turn and reject late IM sends.
6. Verify delivery: response event type, attachment count, and at least one image URL HTTP 200 image content-type.
7. If Xiaoduiyou IM delivery fails with a platform/runtime error (for example `TURN_ALREADY_CLOSED`, missing attachments despite correct `xiaoduiyou_im_send`, or frontend cannot display supported image payloads), do not keep silently retrying or blame the user. Briefly explain that this looks like a platform issue, encourage the user to keep using the product and to submit feedback when convenient, and provide a concise copy-pasteable bug report with environment/session, repro steps, actual/expected result, and exact error.
8. For product questions: Xiaohongshu provides lived-experience/reference evidence; Taobao/Tmall provides buyable candidates/parameters.
9. For document/content-package artifacts, travel plans, publish tabs, or process docs, load `xiaoduiyou-doc-content-package`; do not keep that workflow inside IM.
10. For Growth Diary records, load `xiaoduiyou-growth-diary`; do not send diary-only data as generic chat cards unless the user asks for a chat preview.
11. Keep private family context out of skill files. In a local Hermes environment, read or create `${HERMES_HOME:-$HOME/.hermes}/private/xiaoduiyou-family-care-preferences.md` for family-specific names, IDs, childcare preferences, and durable care-history facts. Update that file when the user gives durable private preferences; keep reusable product behavior in this skill. This path is outside `skills/` and `plugins/` so skill upgrades should not overwrite it.

## Case map owned by IM

| User says / situation | Open/use | Why |
|---|---|---|
| `给我视觉卡片` / `卡片` / `点图片打开` | `xiaoduiyou_im_send` + `references/visual-card-delivery.md` | Backend assetizes images and sends clickable `image_attachments`. |
| `淘宝上找一下...给我` / `淘宝上找一下...给我卡片` | `references/product-question-workflow.md` then `references/visual-card-delivery.md` | Product research plus clickable candidate cards. |
| `小红书找参考帖` / source examples | `references/product-question-workflow.md` and `references/visual-card-delivery.md` | Source/reference cards and links. |
| Runtime send/message/card payload details | `references/runtime-api-reference.md` | Chat message endpoint and `image_attachments` payloads. |
| Asset upload/image URL verification for chat cards | `references/image-upload-contract.md` | Upload local/generated images before final UI use. |
| Runtime turn lifecycle / message stream state | `references/runtime-turn-lifecycle.md` | Debug or reason about Agent 对话页 runtime turns. |
| Child profile/development: name/birthday/gender/allergy/height/weight/photo/skill nodes | load `xiaoduiyou-child-profile` | Profile and development writes use `xiaoduiyou_child_get` and `xiaoduiyou_child_patch`. |
| Scheduled Xiaoduiyou message / reminder / cron delivery | `cronjob(action="create")` with `deliver` | Cron runs without `send_message`; delivery target must be encoded in `deliver`. |
| Explicit `session_purpose: feedback` or configured public feedback Agent/profile | load `xiaoduiyou-feedback-issues` | Feedback triage is public-Agent-only; ordinary chat mentioning feedback stays in IM. |

## First-pass routing

| User intent in Agent 对话页 | Route |
|---|---|
| Visual/clickable image cards | handle here; open `references/visual-card-delivery.md` |
| Product questions: XHS + Taobao/Tmall + cards | handle here; open `references/product-question-workflow.md` |
| Runtime endpoints and message payloads | handle here; open `references/runtime-api-reference.md` |
| Upload/verify images | handle here; open `references/image-upload-contract.md` |
| Scheduled message/reminder to a Xiaoduiyou channel | use `cronjob(action="create")` with `deliver`; do not schedule a future `send_message` call |
| Baby/toddler parenting guidance without record writes | answer in chat; use the parenting guidance rules below |
| Child profile or development progress update/query | load `xiaoduiyou-child-profile` |
| Explicit `session_purpose: feedback` or configured public feedback Agent/profile | load `xiaoduiyou-feedback-issues` |
| Document/content-package artifacts, travel plans, publish tabs, process docs | load `xiaoduiyou-doc-content-package` |
| 成长日记 / diary records / diary photos | load `xiaoduiyou-growth-diary` |

## Parenting Guidance In Chat

Use this section for Xiaoduiyou chat answers about baby/toddler development, parenting decisions, family caregiving patterns, routines, feeding/sleep cooperation, emotion, behavior, discipline, play, and early education when the user is not asking to write records.

- Before relying on family-specific facts such as child nickname, caregiver labels, developmental history, Feishu IDs, or household preferences, check `${HERMES_HOME:-$HOME/.hermes}/private/xiaoduiyou-family-care-preferences.md` when running in local Hermes. If it is missing and the user provides durable private context, create it there instead of adding that data to this skill.
- Give modern, evidence-based, non-stereotyped advice. Do not rely on gender scripts such as "mother = naturally sensitive/caretaking" or "father = naturally strong/decision-maker." Infer only from observed behavior, stated context, and explicit uncertainty.
- Explain behavior through several lenses together: developmental stage, attachment, learning/routines, cognition, emotion coaching, environment design, caregiver consistency, and family-system fatigue or conflict.
- Structure substantial advice as: conclusion first, developmental task, what adults should do, what adults should avoid, home implementation, and uncertainty/red flags.
- Use concrete caregiver scripts: name the emotion, validate the wish, hold the boundary, and offer an acceptable alternative. Avoid shame, threats, ridicule, abandonment, inconsistent rules, or unsafe freedom.
- For advanced toddlers or order-sensitive-period signs, reason from actual age plus the near-next stage. If motor ability is ahead, raise the safety bar because reachable hazards increase before impulse control catches up.
- For pediatric symptom or medical-like threads, treat the conversation as a case note: restate timeline/facts, separate facts from inferences, rank likely causes/modifiers, and update the conclusion only when new information changes the evidence. Do not diagnose from photos alone. For current guideline or medication-dose claims, use authoritative live sources or tell the user the claim needs medical confirmation.
- If the user wants to log, correct, summarize, or query care events, switch to `xiaoduiyou-growth-diary`.

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
