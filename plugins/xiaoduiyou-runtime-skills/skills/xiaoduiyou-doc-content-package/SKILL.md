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
2. Visible result tabs render from `ui_templates` + `fields.publish_notes`; process/evidence material stays in `source_markdown`, `body`, or process blocks.
3. Images referenced by publish tabs must be durable browser-accessible URLs; upload local/generated/source images through `/api/assets` first.
4. Keep the final publish tabs clean: final copy/images only, no process notes, no raw evidence dumps, no secrets.
5. For chat visual cards only, use `xiaoduiyou-im`; do not create a document unless explicitly requested.
6. For 成长日记 records, use `xiaoduiyou-growth-diary`; do not encode diary records as content packages.

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
