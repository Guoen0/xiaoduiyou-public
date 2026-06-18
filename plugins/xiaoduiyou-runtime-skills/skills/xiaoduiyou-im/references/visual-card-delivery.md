# Xiaoduiyou visual-card delivery

Use this when a Xiaoduiyou user asks for “视觉卡片”, clickable image cards, source cards, or “点图片打开链接”.

## Non-negotiable trigger

If `Current Session Context` says `Source: Xiaoduiyou`, or the user-visible screen is an `Agent 对话页`, and the user asks for `视觉卡片` / `卡片` / clickable product/reference images, this workflow is mandatory. A browser screenshot, local file path, `MEDIA:/...`, Markdown image, or plain link-only response is a failed delivery even if the image itself looks correct.

This also applies to plain "生成图片 / 做张图 / 画一个..." requests in Xiaoduiyou chat. Generate the image with the appropriate creative/image skill, then deliver it via this workflow in the same active turn. Do not return `/Users/...`, `/tmp/...`, or Markdown image syntax as the final answer.

## Key lesson

Do not send Xiaoduiyou visual cards as `MEDIA:/...`, Markdown images, or raw text links. Generic Hermes media attachments can be omitted by the Xiaoduiyou messaging channel and will not exercise the Xiaoduiyou card renderer.

If the user says “视觉卡片” while the current screen is a Xiaoduiyou Agent conversation, treat it as a request for Xiaoduiyou structured visual cards, not a standalone screenshot. If the user then says “你发啊”, stop explaining and send the cards immediately.

The correct path is `xiaoduiyou_im_send`:

1. Prepare one image per card. For generated images, use `data:image/png;base64,...`; for existing web images, use durable `https://` URLs. Do not pass local paths.
2. Call `xiaoduiyou_im_send` with `content[]` parts. Omit `session_id` for background/default delivery; Xiaoduiyou routes to the Home `default` channel, shown to users as `主对话`. Pass `session_id` only when targeting a specific active session.
   - `input_text` for the card intro text.
   - `input_image` with `image_url`, `detail`, and Xiaoduiyou `display` metadata (`title`, `subtitle`, `badge`, `link_url`).
3. Let Xiaoduiyou backend upload/assetize images and emit the final `image_attachments[]`.
4. Verify the tool result has the expected attachment count.
5. Verify at least one returned asset URL is browser-accessible (HTTP 200, image content-type) when the URL is returned/visible before claiming the card is delivered.
6. If delivery fails because of a Xiaoduiyou platform/runtime issue (for example `TURN_ALREADY_CLOSED`, image attachments missing from a successful-looking response, or the frontend cannot display valid image payloads), stop looping after a small number of retries. Tell the user this appears to be a platform problem, encourage them to keep using Xiaoduiyou and submit feedback when convenient, and provide a copy-pasteable issue report with: current environment/session/channel, what the user asked for, exact tool payload shape at a high level, actual error, expected behavior, and why it matters.

Example tool payload:

```json
{
  "channel": "default",
  "content": [
    { "type": "input_text", "text": "龙柳小红书视觉卡片，点图片可打开原帖。" },
    {
      "type": "input_image",
      "image_url": "https://example.com/cover.webp",
      "detail": "auto",
      "display": {
        "title": "龙柳参考帖",
        "subtitle": "小红书 · 真实经验",
        "link_url": "https://www.xiaohongshu.com/explore/xxxx",
        "badge": "参考帖"
      }
    }
  ]
}
```

## Legacy Script

Use the bundled script only for old Hermes/OpenClaw installs where `xiaoduiyou_im_send` is unavailable:

```bash
HERMES_SKILL_HOME="${HERMES_HOME:-$HOME/.hermes}"
python "$HERMES_SKILL_HOME/skills/xiaoduiyou/xiaoduiyou-im/scripts/send_visual_cards.py" --list-channels
python "$HERMES_SKILL_HOME/skills/xiaoduiyou/xiaoduiyou-im/scripts/send_visual_cards.py" \
  --channel default \
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
