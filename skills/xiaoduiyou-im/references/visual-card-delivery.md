# Xiaoduiyou visual-card delivery

Use this when a Xiaoduiyou user asks for “视觉卡片”, clickable image cards, source cards, or “点图片打开链接”.

## Non-negotiable trigger

If `Current Session Context` says `Source: Xiaoduiyou`, or the user-visible screen is an `Agent 对话页`, and the user asks for `视觉卡片` / `卡片` / clickable product/reference images, this workflow is mandatory. A browser screenshot, local file path, `MEDIA:/...`, Markdown image, or plain link-only response is a failed delivery even if the image itself looks correct.

## Key lesson

Do not send Xiaoduiyou visual cards as `MEDIA:/...`, Markdown images, or raw text links. Generic Hermes media attachments can be omitted by the Xiaoduiyou messaging channel and will not exercise the Xiaoduiyou card renderer.

If the user says “视觉卡片” while the current screen is a Xiaoduiyou Agent conversation, treat it as a request for Xiaoduiyou structured visual cards, not a standalone screenshot. If the user then says “你发啊”, stop explaining and send the cards immediately.

The correct path is:

1. Resolve the real backend `session_id` with the Agent token (`scripts/send_visual_cards.py --list-sessions`). If the runtime prompt/current screen already gives a concrete session such as `sess_0053`, still list sessions once when practical and confirm it exists; do not rely on a visible title unless it matches a listed `session_id`.
2. Prepare one image per card. For quick product-answer cards, generated/PIL/HTML-rendered source images are fine, but avoid emoji glyphs unless verified — Chinese/system fonts may render emoji as tofu squares. Prefer text badges or simple Chinese characters for deterministic legibility.
3. Upload every local/generated/remote source image to Xiaoduiyou `/api/assets` with `session_id`.
4. Send a session message to `/api/agent/sessions/{session_id}/messages` with:
   - `text` / `detail`
   - `image_urls`
   - `image_attachments[]` containing `image_url`, `link_url`, `title`, `subtitle`, `badge`
5. Verify the response event is `agent.progress` and its payload contains the expected `image_attachments` count.
6. Verify at least one returned asset URL is browser-accessible (HTTP 200, image content-type) before claiming the card is delivered.

## Script

Use the bundled script instead of hand-writing one-off POST/upload code:

```bash
HERMES_SKILL_HOME="${HERMES_HOME:-$HOME/.hermes}"
python "$HERMES_SKILL_HOME/skills/productivity/xiaoduiyou-im/scripts/send_visual_cards.py" --list-sessions
python "$HERMES_SKILL_HOME/skills/productivity/xiaoduiyou-im/scripts/send_visual_cards.py" \
  --session-id sess_0005 \
  --text '龙柳小红书视觉卡片，点图片可打开原帖。' \
  --cards-json /tmp/cards.json
```

`/tmp/cards.json` shape:

```json
[
  {
    "image_path": "/tmp/cover.webp",
    "title": "龙柳参考帖",
    "subtitle": "小红书 · 真实经验",
    "link_url": "https://www.xiaohongshu.com/explore/xxxx",
    "badge": "参考帖"
  }
]
```

Remote images may use `image_url` instead of `image_path`; the script will download then assetize them.

## Review/local fallback

Prefer remote/TOS asset storage. If a review/local environment returns `IMAGE_STORAGE_NOT_CONFIGURED`, `--allow-local-storage` can be used for a smoke test only when the resulting app-local URL is publicly accessible from the current frontend origin.

Do not turn that fallback into the default for production-like answers.
