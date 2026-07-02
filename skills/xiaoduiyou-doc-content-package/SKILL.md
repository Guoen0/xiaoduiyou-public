---
name: xiaoduiyou-doc-content-package
description: "Xiaoduiyou document/content-package workflow for creating, updating, validating, and delivering artifacts with ui_templates, publish_notes, source_markdown, process docs, travel plans, Xiaohongshu/Moments publish tabs, and document actions. Use when the user asks for 旅游规划/旅行规划, 内容包, 文档产物, document artifact, publish-ready package, 小红书/朋友圈发布稿 tabs, or Xiaoduiyou document create/update/delete operations."
---

# Xiaoduiyou Doc Content Package

This skill owns Xiaoduiyou document artifacts and content packages. It is separate from chat/IM cards and separate from Growth Diary records.

## Trigger

Load this when the user asks for:

- `内容包`, `文档`, `文档产物`, `过程文档`, `旅游规划`, `旅行规划`, `行程规划`, `发布稿`, `小红书发布稿`, `朋友圈发布稿`.
- Create/update/delete a Xiaoduiyou document.
- A result that should render as `ui_templates` / `publish_notes` tabs, including `travel_plan`.
- Process/evidence material that should be preserved as `source_markdown` or document body.

## Non-negotiables

1. Only call Xiaoduiyou document tools when the user explicitly asks for a document artifact or mutation.
2. Distinguish **plain documents** from **content packages**. If the user says `只写文档`, `只要文档`, `普通文档`, or does not ask for publish tabs/templates, call `xiaoduiyou_documents_create` with only `title` + `body`/`block_json`; **omit** `ui_templates`, `fields.ui_templates`, and `fields.publish_notes` entirely. Do not create empty publish fields “just in case.”
3. Visible result tabs render from `ui_templates` + `fields.publish_notes`; process/evidence material stays in `source_markdown`, `body`, or process blocks.
4. Images referenced by publish tabs must be durable browser-accessible URLs; upload local/generated/source images through `/api/assets` first.
5. Keep the final publish tabs clean: final copy/images only, no process notes, no raw evidence dumps, no secrets.
6. For chat visual cards only, use `xiaoduiyou-im`; do not create a document unless explicitly requested.
7. For 成长日记 records, use `xiaoduiyou-growth-diary`; do not encode diary records as content packages.
8. If publish tabs were accidentally attached and `patch_fields` with `ui_templates: null` / `publish_notes: null` makes `view=field` return null but `summary.fields_keys` still contains those keys or the frontend still displays Xiaohongshu/Moments tabs, stop retrying and report a product bug. The likely fix is backend true key deletion or frontend gating on non-empty `ui_templates` plus matching `publish_notes`, not merely `fields_keys`/historical state.

## Case map owned by Doc Content Package

| User says / situation | Open/use | Why |
|---|---|---|
| `旅游规划` / `旅行规划` / itinerary artifact | `references/travel-plan-planning-workflow.md` then `references/travel-plan-result-template.md` | Travel planning is a document/content artifact with process evidence and structured `travel_plan` UI data. |
| Travel plan Xiaohongshu reference images | `references/travel-plan-xhs-reference-workflow.md` | Travel artifacts need durable uploaded reference images and clean provenance. |
| `做成内容包` / `创建文档` / `文档产物` | `references/content-package-contract.md` | Document artifact / `ui_templates` / `publish_notes` contract. |
| `小红书发布稿` / `朋友圈发布稿` / publish tabs | `references/social-publish-result-template.md` | Platform-specific publish tab shape. |
| Process/evidence doc Markdown fidelity | `references/process-document-markdown.md` | Keep process material separate and well-formed. |
| Validate a content-package JSON before callback/document update | Prefer the first-class document tools' payload schema; optional local lint only if the script is present | Catch local paths, mismatched templates, process/result mixing. |
| `更新这个文档` / `删掉文档` | Tool-use section below + `references/runtime-api-reference.md` | Explicit document mutation. |
| Asset upload/image URL verification for document tabs | `references/image-upload-contract.md` | Publish tabs need durable browser-accessible image URLs. |

## Fast routing

| Need | Open |
|---|---|
| Travel planning artifact workflow | `references/travel-plan-planning-workflow.md` |
| Structured `travel_plan` result template | `references/travel-plan-result-template.md` |
| Xiaohongshu reference-image workflow for travel plans | `references/travel-plan-xhs-reference-workflow.md` |
| Content-package schema and `ui_templates` / `publish_notes` contract | `references/content-package-contract.md` |
| Social publish tab shape for Xiaohongshu/Moments | `references/social-publish-result-template.md` |
| Process document Markdown fidelity | `references/process-document-markdown.md` |
| Runtime/document/action endpoints | `references/runtime-api-reference.md` |
| Upload and verify images/assets | `references/image-upload-contract.md` |

## Validation

- Prefer the first-class document tools for read/create/update/delete: `xiaoduiyou_documents_get`, `xiaoduiyou_documents_create`, `xiaoduiyou_documents_update`, `xiaoduiyou_documents_delete`.
- Before calling them, manually validate: `ui_templates` matches `fields.publish_notes`, visible publish tabs contain only final material, and all images are browser-accessible `http(s)` URLs.
- A local validator script may exist in some Hermes installs as an optional lint aid, but public Xiaoduiyou usage skills must not depend on scripts being available.

## Tool use

- Use `xiaoduiyou_documents_create` only for new requested documents/artifacts.
- Use `xiaoduiyou_documents_update` only for explicit edits/append/patches.
- Use `xiaoduiyou_documents_delete` only when explicitly asked to delete.
- Use `xiaoduiyou_documents_get` with default `view=summary`; use `view=field` for one field or `view=blocks` for paged blocks. Use `view=full` only when explicitly necessary.
- When updating a content package that has publish tabs, keep the process document and `fields.publish_notes.<template>` synchronized in the same operation. For Xiaohongshu, write the complete note shape (`platform`, `label`, `title`, `body`, `hashtags`, `images`, and any `image_plan`) plus `ui_templates: ["xiaohongshu"]`; partial `title/body` patches may not render in the publish page.
- When generating multi-image Xiaohongshu carousel assets, use `delegate_task` subagents for independent image generation instead of serial `image_generate` calls. Define the shared visual system and exact per-image prompts in the parent, then spawn one subagent per image to call `image_generate` only. After generation, normalize/verify image dimensions before upload; the image backend's nominal `portrait` can return inconsistent real pixel sizes, so inspect actual files and standardize to the target ratio (usually 3:4 / 1080×1440 for Xiaohongshu) before writing `publish_notes.xiaohongshu.images`.
- Use `xiaoduiyou_documents_get` with default `view=summary`; use `view=field` for one field or `view=blocks` for paged blocks. Use `view=full` only when explicitly necessary.

## Xiaohongshu content-package editing pitfalls

- When editing a content package that has a Xiaohongshu publish tab, update **both** the process document body/blocks and `fields.publish_notes.xiaohongshu`. Do not assume the publish page parses the process document. The publish tab renders from structured fields.
- When rebuilding document blocks from Markdown/source text, do not duplicate the document title: if the tool/document already has a top-level `title` or first `heading` block, remove any extra literal Markdown H1 paragraph like `# <same title>` before writing blocks.
- For `publish_notes.xiaohongshu`, write the complete shape: `platform: "xiaohongshu"`, `label: "小红书发布稿"`, `title`, `body`, `hashtags`, `images` (array, even empty if images are not ready), and any `image_plan`. Missing `platform`/`label` can make the publish page appear empty or stale even when `title/body` exist in storage.
- If the user asks to shorten or humanize正文, keep the process doc and publish tab in sync in the same update. Avoid stiff process-document language in user-facing sections; use natural Xiaohongshu copy with one clear human point per paragraph.
- When generating images for a publish tab, after QA upload local generated files to Xiaoduiyou/TOS, verify the HTTPS URLs, then patch `publish_notes.xiaohongshu.images` in the final publishing order. Do not leave generated images only as local `MEDIA:`/cache paths.
- Also preserve generated images as process-document history so users can revert or compare later. Do not store only raw links. For many tall social images, prefer a compact rendered layout over five full-height images stacked vertically. If the platform supports `image_grid`, use that rather than a stitched contact sheet: `{"type":"image_grid","props":{"columns":2,"gap":12,"images":[{"url":"https://...","caption":"..."}]}}`. Keep each image as an independent URL so users can preview, reuse, replace, or roll back a single page.
- **Never drop historical generated images while editing a content package.** When replacing/regenerating one carousel page, treat `历史生图参考` as append-only unless the user explicitly asks to clean it up: preserve all previous candidates, stretched/cropped variants, contact sheets, and discarded versions in a visible `image_grid` with captions. Do not replace a history grid with only the latest 2–3 items; users often have no other way to recover or compare those images.
- Place images according to their role, not just where history was appended. Current/final carousel images belong in the `发布笔记` area, usually under a `### 最终配图` subsection near title/body/hashtags. `历史生图参考` is only for old candidates, discarded versions, contact sheets, or rollback notes. Do not put the active final image set under history just because it was generated during the session.
- When swapping/reverting one carousel image, prefer `xiaoduiyou_documents_update(command="replace_publish_image", platform="xiaohongshu", index=<1-based>, image_url=..., history_caption=..., sync_process_doc=true, base_revision=<live revision>)`. It updates `publish_notes.xiaohongshu.images[index]` and the process document `image_grid` together. If a user says an older candidate is better, prefer reverting to that exact URL unless they explicitly ask for a new generation.
- Use `upsert_image_grid` to create/replace the final image grid from explicit images, and `sync_publish_images_to_document` to rebuild the document grid from live publish-note images. Prefer these narrow commands over broad `overwrite` when only images changed.
- If an otherwise-good image has black side bars from prior normalization, a safe fast fix is: crop the non-black bounding box, resize/contain to the target ratio (usually 1080×1620), upload the processed file to TOS, HEAD-verify it, then replace only that image URL in both publish notes and document grids. Label the original black-bar version in history for rollback.
- When normalizing generated social images to a requested ratio, inspect the real source pixel sizes first. For Xiaohongshu vertical drafts, common targets include 3:4 (1080×1440) and 2:3 / 1:1.5 (1080×1620). If preserving content, use a contain fit so titles and subjects are not cropped. Do not add decorative blurred/extended backgrounds unless the user asks for that style; a safer neutral treatment is to height-fit or width-fit the image and fill the remaining canvas with a plain dark/black background similar to Xiaohongshu dark mode. Upload the normalized URLs, replace `publish_notes.xiaohongshu.images`, and update the process-document final-image grid/history in the same pass.
- To embed an image in Xiaoduiyou `block_json`, use the BlockNote-compatible shape `{"type":"image","props":{"url":"https://...","caption":"...","name":"...","showPreview":true,"previewWidth":360}}`. A bare block like `{"type":"image","url":"..."}` may be stored but not render correctly. If multiple images should display compactly, use `image_grid` instead of separate `image` blocks once the platform supports it. If converting Markdown image syntax, make sure the normalizer or document update produces the right `props.url` or `image_grid.props.images[].url` shape.
- If the user reports "发布页还是没有" or that platform images did not change, immediately read `publish_notes.xiaohongshu` with `view=field` and compare the live `images` array against the intended URLs. If the field is stale, use `replace_publish_image` for one image or `patch_fields` for full publish-note copy. Document updates may be queued for final callback, so treat tool success as queued until a later read/screen summary confirms the visible field.
- Avoid mixing a direct `patch_fields` call with a subsequent broad `overwrite` built from stale document state in the same turn. Xiaoduiyou may reject same-callback conflicting overwrites; when overwrite is unavoidable, read live summary first and pass `base_revision`.
- When preserving iteration history, make discarded/generated images visible in the process document with an `image_grid` under a clearly labeled history section. Do not leave history as prose saying links exist; users need to see thumbnails in the document. Clearly distinguish `最终配图` (active publish images) from `历史生图参考` (old candidates, discarded versions, comparison sheets, rollback material).

## Xiaoduiyou copy style and publish-tab sync

- When editing Xiaoduiyou process docs or social publish copy, write like a person talking to another caregiver, not like a content-strategy memo. Prefer concrete scenes, short spoken Chinese, and lived details. Avoid stiff phrases such as `定位`, `目标：`, `围绕...展开`, `结构化产物`, `系统/能力/协作` unless the user explicitly asks for process analysis.
- For Xiaohongshu-style product notes, lead with lived human tension before product logic. Convert “we built X / product does Y” into “the reader is stuck in this real moment, so X quietly helps.” Prefer first-person perception (`我越来越觉得`), concrete scene fragments, and one emotionally recognizable pressure point before naming the product.
- Ground abstract benefits in observable evidence. If the benefit is “scientific parenting,” explain why the tiny records matter as state signals (milk, sleep, poop, food reactions, vaccines, growth changes) instead of merely listing features. If the benefit is “collaboration,” first show the repeated context-transfer moment, then let the collaboration idea emerge.
- Avoid making the product the hero too early. For first-touch social posts, the hero is the caregiver’s mental load; the product should appear as a small relief action with exact user input examples (`刚喝了 180ml 奶`, `下午拉了一次，偏稀`) and the immediate outcome (`记进成长日记`).
- Keep family conflict sympathetic and specific. Do not flatten dad/mom into villain/victim roles; use scenes like “爸爸问我现在该干啥” plus the actual missing context. This preserves relatability without turning the copy into blame.
- Prefer endings that lower anxiety and name the smallest useful step (`先让信息别丢`, `让判断有依据`, `记录不再继续消耗一个人`) over broad strategy language such as `再谈家庭协作`, `家庭系统`, or `AI 管家`.
- Treat the process document itself as a user-facing working artifact, not just a hidden prompt dump. The doc should help the user review and reuse the content: include what the piece is saying, final publish copy, final images, visual direction, image structure, and history/rollback references in clearly separated sections.
- For Xiaohongshu image sections, make the final images visible in the document, not just stored in `publish_notes.images`. Use `image_grid` with captions, keep the images in publish order, and label why each page exists. The user should be able to judge the carousel by looking at the document alone.
- Separate image roles explicitly: `最终配图` for currently active publish images; `图片风格` for the shared visual language; `图片结构建议` for per-page intent; `历史生图参考` for discarded/older candidates. Do not mix final images, style notes, and iteration history into one vague section.
- Visual direction should be concrete and anti-generic: name the desired style, palette, composition, emotional click point, and avoid list. For Xiaoduiyou parenting notes, prefer lived home scenes, chunky hand-drawn characters, sticky notes/chat bubbles/checklists, readable large Chinese titles, and warm cream/yellow/orange tones; avoid blue-purple SaaS/dashboard/AI-tech aesthetics unless explicitly requested.
- Captions for generated images should describe the communicative job of the page (`有记录，有线索，心里更有底`, `脑子里开着小窗口`) rather than merely restating file names. Preserve old candidates visibly with captions so the user can compare, revert, or point to a specific page.
- If the user says the正文/发布稿/文档/图片“不像人话” or “不像能发的内容包”, read the current document and update both text and document presentation surfaces in the same pass: process blocks, `publish_notes.<template>`, final image grid, and history grid as needed. Do not only answer with advice.
- For content packages with `ui_templates`, process document and publish page are separate surfaces. Updating `block_json` alone does not update the 小红书/朋友圈 tab. Whenever a rewrite affects final copy, update `fields.publish_notes.<template>` too.
- Xiaohongshu publish notes should be written with the full contract, not a partial object: include `platform: "xiaohongshu"`, `label: "小红书发布稿"`, `title`, `body`, `hashtags`, and `images` when available. Keep optional planning fields such as `image_plan` out of the body.
- After a publish-tab update, read `publish_notes.<template>` with `view=field` before reporting success when the tool can return the applied state. If the update is queued for final callback, say it is queued/applied to the callback rather than claiming the visible tab has already refreshed. If the field shows new copy but the UI tab still shows old content, treat it as a frontend/rendering or refresh bug instead of repeatedly patching the same partial fields.
