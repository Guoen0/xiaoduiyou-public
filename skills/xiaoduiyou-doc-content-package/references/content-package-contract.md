# Xiaoduiyou content-package contract

Use this when a connected Agent creates, revises, or validates Xiaoduiyou content-package artifacts/documents. The visible result pages render from structured fields; the process document is for evidence and editing.

## Artifact schema

Use schema `xdy.artifact_blocks.v1` for content packages.

Typical `blocks` fields:

- `title`
- `body`
- `visual_direction`
- `image_order`
- `generated_images`
- `hashtags`
- `reply_drafts`
- `compliance_notes`
- `source_markdown`
- `ui_templates`
- `publish_notes`
- `product_research` — optional structured evidence for product Q&A: Xiaohongshu reference posts, Taobao/Tmall candidates, clean links, and uploaded card images.

`ui_templates` is the Agent-selected list of result UI templates to render. Currently supported values:

- `xiaohongshu`
- `moments`
- `travel_plan` — travel-planning execution UI: destination gallery, journey time, real maps, hotel cards, itinerary, baby rhythm.

The Agent may select one or more templates when creating a content package, and may change the list later through `xiaoduiyou_documents_update(command="patch_fields", ui_templates=[...])` or by setting `fields.ui_templates`.

Preferred platform publish fields must match selected templates:

- `publish_notes.xiaohongshu`
- `publish_notes.moments`
- `publish_notes.travel_plan`

Legacy `publish_note` is only a Xiaohongshu compatibility alias when creating a new artifact. Do not rely on it as the primary model.

## Process/result separation

The process document is no longer the editable source of truth for publish results. Result pages are filled by structured fields and rendered by selected UI templates.

Use this split:

- `fields.ui_templates` / `blocks.ui_templates`: which result templates to show.
- `fields.publish_notes.<template>` / `blocks.publish_notes.<template>`: final result data for each selected template.
- `block_json` and `source_markdown`: process-only material such as references, reasoning, source evidence, image rationale, and visual direction.

Do not put final publish sections into the process document. Avoid these legacy headings:

- `小红书发布稿（编辑这里会同步到发布页）`
- `朋友圈发布稿（编辑这里会同步到发布页）`
- `发布稿标题`
- `发布稿图片`
- `发布稿正文`

Saving or updating the process document should not derive, overwrite, or backfill `publish_note`, `publish_notes`, or `generated_images` from process blocks.

## Tool usage for template selection

When creating a content package via `xiaoduiyou_documents_create`, pass:

- `ui_templates`: selected templates, e.g. `["xiaohongshu", "moments"]`, `["moments"]`, or `["travel_plan"]` when the result should render as a travel-planning execution UI.
- `fields.publish_notes`: final result data for exactly those platforms/templates unless the user asks for more; for `travel_plan`, include structured `fields.publish_notes.travel_plan.travel_plan` data.
- `fields.source_markdown` and/or `block_json`: process-only document content.

When revising which result pages should exist, call `xiaoduiyou_documents_update` with `command="patch_fields"`, `ui_templates=[...]`, and updated `fields.publish_notes` as needed. To remove a template from display, remove its key from `ui_templates`; preserving old `publish_notes` data is allowed as hidden history unless the user asks to delete it.

## Platform publish contracts summary

### Xiaohongshu

- Select `ui_templates: ["xiaohongshu"]` or include it alongside other templates.
- `title`: short final title only.
- `images`: final image URLs in publishing order; the first image is always the feed cover.
- `body`: ready-to-copy Chinese body. Include hashtags inline at the end if needed.
- `hashtags`: evidence-based tags. Preserve required series tags when the user's project provides them.
- Full contract: `references/social-publish-result-template.md`.

### Moments

- Select `ui_templates: ["moments"]` or include it alongside other templates.
- `body`: ready-to-copy Moments text only.
- `images`: same final images or a platform-specific subset if requested.
- No title/hashtag field is required.
- Full contract: `references/social-publish-result-template.md`.

### Product question / purchase research

- Do not force generic social/travel templates unless the user asks for a social post or travel plan.
- Use chat `image_attachments` for clickable visual cards; use `source_markdown` and optional `product_research` for persistent evidence.
- Xiaohongshu links are `参考帖` / experience evidence; Taobao/Tmall links are `商品候选` / purchase-parameter evidence.
- Rendered source images must be uploaded to Xiaoduiyou assets; source/product links should be clean and clickable.
- Full workflow: `references/product-question-workflow.md`.

### Travel Plan

- Select the template with `ui_templates: ["travel_plan"]` or include it alongside other templates if needed.
- Store structured data at `publish_notes.travel_plan.travel_plan`; do not expect the UI to parse the process document.
- Required emphasis: destination gallery, origin-to-destination time/map, concrete highlights when useful, hotel-to-POI map, hotel cards with names/images/facilities/links, short itinerary, and baby rhythm when relevant.
- Destination/reference images must be durable Xiaoduiyou/TOS/asset URLs. Do not use local paths, repository `public` paths, `/official`, `/replay-images`, or temporary CDN hotlinks as rendered image fields.
- When using Xiaohongshu/reference images, keep `destination.images[]` and `destination.image_links[]` one-to-one so the UI can render per-image source CTAs.
- Use checked real map coordinates (`lng`/`lat`) for origins, stations, hotels, and POIs; hotel-selection maps should show relative marker positions rather than arbitrary connecting lines.
- Keep process/research material in `source_markdown`/process blocks; visible result copy should sound natural and must not include internal instruction words such as `关键利益点`, `UI模型`, or `数据接口`.
- Full result contract: `references/travel-plan-result-template.md`.
- Planning workflow, process document, and quality constraints: `references/travel-plan-planning-workflow.md`.
- Xiaohongshu reference workflow: `references/travel-plan-xhs-reference-workflow.md`.

## Validation checklist

- `ui_templates` selects only templates the user/Agent wants rendered.
- Each selected template has matching `publish_notes.<template>` result data; `travel_plan` must include `publish_notes.travel_plan.travel_plan`.
- Publish tabs do not include process headings such as `过程材料`, `图片结构`, prompts, references, or research notes.
- Xiaohongshu first image is the feed cover.
- Publish body includes hashtags inline when needed; no separate topic section is required.
- Moments text is ready to copy and uses images intentionally.
- Every local/generated image has been uploaded and URL-verified.
- `source_markdown` / process document preserves enough source, references, visual direction, and decisions for later QA.
- No credentials or secrets are present in final artifact/document text.
