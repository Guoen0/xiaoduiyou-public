# Xiaoduiyou image upload contract

Use this when a Xiaoduiyou content/document artifact needs generated or local images.

## Hard rule

Xiaoduiyou public/review browser pages cannot load machine-local paths. Never store these as image values:

- `/tmp/...`
- `/Users/...`
- `~/.hermes/cache/...`
- `file://...`
- `MEDIA:...`
- app-server/repository static paths such as `/official/...`, `/public/...`, `/replay-images/...`, or files stored only so the review server can serve them

Official replay/reference/product images must not be stored in the app server repository or served from server static directories. Use local files only as short-lived upload staging, then delete/ignore them; the shipped artifact/replay should reference only TOS/public asset URLs.

## Upload flow

1. Generate or obtain the final image file. For product-link visual cards, obtain the product page/listing's actual first product image; do not substitute a placeholder, generic generated graphic, screenshot crop, local `MEDIA:` file, or raw third-party hotlink as the final card image.
2. Upload it to Xiaoduiyou:
   - endpoint: `POST /api/assets`
   - multipart file field: `file`
   - `source=agent_generated` for Agent-generated output
   - add `session_id` and/or `document_id` when available.
3. Read the response URL:
   - prefer top-level `url` if present;
   - otherwise use `asset.public_url`.
4. Write only that durable browser-accessible URL into:
   - `publish_notes.*.images`
   - legacy `publish_note.images`
   - `generated_images`
   - process sync image blocks;
   - chat `image_urls` and `image_attachments[].image_url`.

## Verification before final callback

For each image URL, run `GET` or `HEAD` against the Xiaoduiyou origin. Expected:

- HTTP status `200`
- `content-type` starts with `image/`
- URL does not contain local path patterns (`/tmp/`, `/Users/`, `.hermes/cache`, `file://`, `MEDIA:`)

If any image fails, upload/replace it before completing the turn.

## Security

The Agent never needs TOS/OSS/S3 credentials. Xiaoduiyou backend owns storage credentials and account scoping. Do not expose AK/SK/tokens/connection strings; redact accidental source text as `[REDACTED]`.
