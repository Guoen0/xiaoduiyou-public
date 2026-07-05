# Xiaoduiyou image upload contract

Use this when a Xiaoduiyou content/document artifact needs generated/local images or needs to decide whether an existing web image can be used directly.

## Hard rule

Xiaoduiyou public/review browser pages cannot load machine-local paths. Never store these as image values:

- `/tmp/...`
- `/Users/...`
- `~/.hermes/cache/...`
- `file://...`
- `MEDIA:...`
- app-server/repository static paths such as `/official/...`, `/public/...`, `/replay-images/...`, or files stored only so the review server can serve them

Official replay/reference/product images must not be stored in the app server repository or served from server static directories. Use local files only as short-lived staging, then delete/ignore them. The shipped artifact/replay should reference browser-fetchable HTTPS URLs, which can be either Xiaoduiyou asset URLs or stable external image URLs.

## Upload flow

For chat-only visual cards, prefer `xiaoduiyou_im_send` and pass `https://` or `data:image/...;base64,...`; Xiaoduiyou backend uploads/assetizes the image and emits `image_attachments`. Existing public HTTPS image URLs from web search, Taobao, Xiaohongshu, or Google Images may be passed directly when they are fetchable without cookies/login and are not local, blob, or temporary machine paths.

For local/generated files that need durable URLs, use the first-class connector tool `xiaoduiyou_assets_upload` when available. It accepts `file_path`, optional `file_name`/`mime_type`, `source`, and `require_remote_storage`, then returns top-level `url` plus `asset` metadata. It does not bind the asset to a session, turn, or document; use the returned URL in the next IM, document, diary, or content-package tool call.

For document artifacts or connectors without `xiaoduiyou_assets_upload`:

1. Generate or obtain the final image file.
2. Upload it to Xiaoduiyou:
   - endpoint: `POST /api/assets`
   - multipart file field: `file`
   - `source=agent_generated` for Agent-generated output
   - add `session_id` and/or `document_id` when available.
3. Read the response URL:
   - prefer top-level `url` if present;
   - otherwise use `asset.public_url`.
4. Write only a browser-accessible HTTPS URL into:
   - `publish_notes.*.images`
   - legacy `publish_note.images`
   - `generated_images`
   - process sync image blocks.

## Verification before final callback

For each image URL, run `GET` or `HEAD` against the Xiaoduiyou origin. Expected:

- HTTP status `200`
- `content-type` starts with `image/`
- URL does not contain local path patterns (`/tmp/`, `/Users/`, `.hermes/cache`, `file://`, `MEDIA:`)

If any local/generated image fails, upload/replace it before completing the turn. If an external source image fails because it is login-bound, anti-hotlinking, expired, or not directly fetchable, either upload a permitted local copy, use a supported `data:image/...` fallback for chat, or omit the image and keep the source link as text.

## Security

The Agent never needs TOS/OSS/S3 credentials. Xiaoduiyou backend owns storage credentials and account scoping. Do not expose AK/SK/tokens/connection strings; redact accidental source text as `[REDACTED]`.
