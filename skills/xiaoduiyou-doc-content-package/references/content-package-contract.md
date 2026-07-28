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
- `ui_payloads`
- `publish_notes`
- `product_research` — optional structured evidence for product Q&A: Xiaohongshu reference posts, Taobao/Tmall candidates, clean links, and uploaded card images.

`ui_templates` is the Agent-selected list of result UI templates to render. Currently supported values:

- `xiaohongshu`
- `moments`
- `travel_plan` — travel-planning execution UI: destination gallery, journey time, real maps, hotel cards, itinerary, baby rhythm.
- `interactive_html` — a self-contained free-form offline HTML page. It is intentionally stateless.
- `mini_app` — a platform-rendered structured mini app with family-shared state.

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
- `fields.ui_payloads` / `blocks.ui_payloads`: non-publish result payloads such as `interactive_html` and `mini_app`.
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

- `ui_templates`: selected templates, e.g. `["xiaohongshu", "moments"]`, `["travel_plan"]`, `["interactive_html"]`, or `["mini_app"]`.
- `fields.publish_notes`: final result data for exactly those platforms/templates unless the user asks for more; for `travel_plan`, include structured `fields.publish_notes.travel_plan.travel_plan` data.
- `fields.ui_payloads.interactive_html`: required when `interactive_html` is selected.
- `fields.ui_payloads.mini_app`: required when `mini_app` is selected.
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

### Interactive HTML

- Select with `ui_templates: ["interactive_html"]` or include it alongside other result templates.
- Store the payload at `fields.ui_payloads.interactive_html`:

```json
{
  "schema": "xdy.interactive_html.v1",
  "label": "互动页面",
  "html": "<!doctype html><html>...</html>"
}
```

- `html` must be one self-contained file with inline CSS and JavaScript.
- Do not use external scripts, stylesheets, APIs, forms, embeds, CDN imports, or remote page URLs. The renderer blocks network access and external navigation.
- Keep the UTF-8 payload below 512 KiB.
- Use ordinary in-page JavaScript state for buttons, inputs, filtering, calculations, and view switching. State resets when the result page is closed or reloaded.
- Do not attempt to access Xiaoduiyou cookies, storage, parent DOM, connector tokens, or APIs. No parent bridge exists in v1.
- Use a short human-readable `label` for the result tab. Do not place process notes or raw evidence in the HTML page.

### Stateful Mini App

- Select with `ui_templates: ["mini_app"]`.
- Store the structured payload at `fields.ui_payloads.mini_app` using the strict schema `xdy.mini_app.v2`. V1 is rejected.
- Include `manifest`, `data`, `state`, `computed`, `actions`, `resources`, and `pages`; do not use the removed V1 keys `label`, `content`, `state_schema`, or `view`.
- Use only declared state, expressions, actions, resources, pages, and platform components. Do not write HTML, JavaScript handlers, an SDK bridge, or `data-xdy-action` attributes.
- Use this mode for reusable search/filter/list/form/statistics/navigation UI and for `session`, `device`, private `member`, or shared `family` state.
- When available, call `xiaoduiyou_mini_app_contract_get` before authoring. Full rules: `references/mini-app-contract.md`; executable starting point: `references/mini-app-v2-example.json`.

## Validation checklist

- `ui_templates` selects only templates the user/Agent wants rendered.
- Each selected publish/travel template has matching `publish_notes.<template>` result data; `travel_plan` must include `publish_notes.travel_plan.travel_plan`.
- `interactive_html` has a valid `ui_payloads.interactive_html` payload using schema `xdy.interactive_html.v1`, a label, and non-empty self-contained HTML below 512 KiB.
- `mini_app` has a valid `ui_payloads.mini_app` payload using schema `xdy.mini_app.v2`, all required V2 top-level objects, declared capabilities/state/actions/pages, and a supported component tree.
- Publish tabs do not include process headings such as `过程材料`, `图片结构`, prompts, references, or research notes.
- Xiaohongshu first image is the feed cover.
- Publish body includes hashtags inline when needed; no separate topic section is required.
- Moments text is ready to copy and uses images intentionally.
- Every final image is URL-verified and browser-accessible; local/generated images have been uploaded or converted before use, while stable public HTTPS source images may be referenced directly.
- `source_markdown` / process document preserves enough source, references, visual direction, and decisions for later QA.
- No credentials or secrets are present in final artifact/document text.
