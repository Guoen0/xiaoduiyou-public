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

Public HTTPS image URLs from web search, Taobao, Xiaohongshu, Google Images, or other source pages may be used directly when they are fetchable without cookies/login and stable enough for the artifact. Upload is required for local/generated files, machine-only screenshots, or external images that are not directly browser-fetchable.

1. Generate or obtain the final local image file.
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

If any local/generated image fails, upload/replace it before completing the turn. If an external source image fails because it is login-bound, anti-hotlinking, expired, or not directly fetchable, either upload a permitted local copy or omit the image and keep the source link as text.

## Security

The Agent never needs TOS/OSS/S3 credentials. Xiaoduiyou backend owns storage credentials and account scoping. Do not expose AK/SK/tokens/connection strings; redact accidental source text as `[REDACTED]`.
