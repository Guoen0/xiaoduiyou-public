# Xiaoduiyou visual-card delivery

Use this when a Xiaoduiyou user asks for “视觉卡片”, clickable image cards, source cards, or “点图片打开链接”.

## Non-negotiable trigger

If `Current Session Context` says `Source: Xiaoduiyou`, or the user-visible screen is an `Agent 对话页`, and the user asks for `视觉卡片` / `卡片` / clickable product/reference images, this workflow is mandatory. A browser screenshot, local file path, `MEDIA:/...`, Markdown image, or plain link-only response is a failed delivery even if the image itself looks correct.

This also applies to plain "生成图片 / 做张图 / 画一个..." requests in Xiaoduiyou chat. Generate the image with the appropriate creative/image skill, then deliver it via this workflow in the same active turn. Do not return `/Users/...`, `/tmp/...`, or Markdown image syntax as the final answer.

## Key lesson

Do not send Xiaoduiyou visual cards as `MEDIA:/...`, Markdown images, or raw text links. Generic Hermes media attachments can be omitted by the Xiaoduiyou messaging channel and will not exercise the Xiaoduiyou card renderer.

If the user says “视觉卡片” while the current screen is a Xiaoduiyou Agent conversation, treat it as a request for Xiaoduiyou structured visual cards, not a standalone screenshot. If the user then says “你发啊”, stop explaining and send the cards immediately.

## Image source rules

`xiaoduiyou_im_send` accepts `input_image.image_url` in exactly two production-friendly forms:

1. A durable, fetchable public `https://...` image URL.
2. A data URL: `data:image/png;base64,...`, `data:image/jpeg;base64,...`, `data:image/webp;base64,...`, or `data:image/gif;base64,...`.

Never pass local paths (`/tmp/...`, `/Users/...`), `file:`, `blob:`, `localhost`, or private-network URLs.

Important JSON shape: `image_url` and `display` are sibling fields on the same `input_image` part. Put the HTTPS URL or `data:image/...;base64,...` string directly in `image_url`. Do not put `image_url` inside `display`; `display` is only metadata such as `title`, `subtitle`, `badge`, and `link_url`.

Correct:

```json
{
  "type": "input_image",
  "image_url": "data:image/jpeg;base64,/9j/4AAQ...",
  "display": {
    "title": "京东儿童玩具",
    "subtitle": "热门儿童玩具推荐",
    "link_url": "https://search.jd.com/Search?keyword=儿童玩具"
  }
}
```

Wrong:

```json
{
  "type": "input_image",
  "display": {
    "image_url": "data:image/jpeg;base64,/9j/4AAQ...",
    "title": "京东儿童玩具"
  }
}
```

External images from Taobao, Tmall, JD/Jingdong, Xiaohongshu, and other sites may fail server-side fetching because of anti-hotlinking, cookies, signed URLs, UA/referrer requirements, or short-lived CDN URLs. A direct HTTPS URL that works in the browser can still fail in Xiaoduiyou with `IMAGE_FETCH_FAILED`. When that happens, do not keep retrying the raw URL. Use one of these alternatives:

- Screenshot or download the image in an allowed local/browser context, then send it as a `data:image/...;base64,...` data URL.
- Upload/assetize the image to durable public/TOS storage first, then pass the resulting HTTPS URL.
- For product cards, use a locally rendered card/screenshot as the image and keep the original product/search page in `display.link_url`.

Prefer JPEG/WebP for large screenshots and keep card images reasonably small. If an inline data URL is too large for the runtime, resize/compress the image or upload it to durable asset storage and pass the public HTTPS URL instead.

The correct path is `xiaoduiyou_im_send`:

1. Prepare one image per card. For generated/local/screenshot images, use `data:image/png;base64,...` or `data:image/jpeg;base64,...`; for existing web images, use durable public `https://` URLs only when they are fetchable without cookies or anti-hotlinking. Do not pass local paths.
2. Call `xiaoduiyou_im_send` with `content[]` parts. Omit `session_id` for background/default delivery; Xiaoduiyou routes to the Home `default` channel, shown to users as `主对话`. Pass `session_id` only when targeting a specific active session.
   - `input_text` for the card intro text.
   - `input_image` with sibling fields: `image_url`, optional `detail`, and Xiaoduiyou `display` metadata (`title`, `subtitle`, `badge`, `link_url`).
3. Let Xiaoduiyou backend upload/assetize images and emit the final `image_attachments[]`.
4. Verify the tool result has the expected attachment count.
5. Verify at least one returned asset URL is browser-accessible (HTTP 200, image content-type) when the URL is returned/visible before claiming the card is delivered.
6. If delivery fails because of a Xiaoduiyou platform/runtime issue (for example `TURN_ALREADY_CLOSED`, `IMAGE_FETCH_FAILED` for anti-hotlinking URLs, image attachments missing from a successful-looking response, or the frontend cannot display valid image payloads), stop looping after a small number of retries. Tell the user this appears to be a platform/problem-with-source-image issue, encourage them to keep using Xiaoduiyou and submit feedback when convenient, and provide a copy-pasteable issue report with: current environment/session/channel, what the user asked for, exact tool payload shape at a high level, actual error, expected behavior, and why it matters.

Example HTTPS tool payload:

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

Example base64/data-URL tool payload:

```json
{
  "content": [
    { "type": "input_text", "text": "这是儿童玩具图片" },
    {
      "type": "input_image",
      "image_url": "data:image/jpeg;base64,/9j/4AAQ...",
      "detail": "auto",
      "display": {
        "title": "京东儿童玩具",
        "subtitle": "热门儿童玩具推荐",
        "link_url": "https://search.jd.com/Search?keyword=儿童玩具"
      }
    }
  ]
}
```

Convert a local screenshot/image to a data URL:

```bash
python - <<'PY'
import base64, mimetypes, pathlib
path = pathlib.Path('/tmp/card.jpg')
mime = mimetypes.guess_type(path.name)[0] or 'image/jpeg'
print(f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode('ascii'))
PY
```

Full Python pattern for screenshot → base64 → tool payload:

```python
# If Playwright is needed for screenshots: python -m pip install playwright && python -m playwright install chromium
import base64, json, mimetypes, pathlib

# Example after creating /tmp/card.jpg via Playwright, browser screenshot, or another renderer.
path = pathlib.Path('/tmp/card.jpg')
mime = mimetypes.guess_type(path.name)[0] or 'image/jpeg'
data_url = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode('ascii')

payload = {
    "content": [
        {"type": "input_text", "text": "这是图片"},
        {
            "type": "input_image",
            "image_url": data_url,
            "display": {
                "title": "标题",
                "link_url": "https://example.com/source"
            }
        }
    ]
}
print(json.dumps(payload, ensure_ascii=False)[:1000])
# Then pass payload["content"] to xiaoduiyou_im_send.
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
