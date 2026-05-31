---
name: xiaoduiyou-usage-workflow
description: Public Xiaoduiyou usage router for connected Agents. Load for Xiaoduiyou runtime usage, then open the matching reference file for content packages, growth diary, images, process docs, product Q&A, or travel/social publish templates.
---

# Xiaoduiyou Usage Workflow

This is the **single public Xiaoduiyou usage skill package** for connected Agents. Keep this `SKILL.md` small: route first, then open the matching reference.

## Boundary

Use only for Xiaoduiyou runtime/product-surface usage:

- receive/poll turns, send progress/final callbacks;
- create/update/delete documents through runtime tools;
- create/revise/validate content-package artifacts;
- answer product questions with Xiaohongshu reference posts, Taobao/Tmall candidates, clean links, and clickable image cards;
- upload local/generated/source images through `/api/assets` before referencing them;
- operate 成长日记 through `/api/growth-diary`.

Do **not** change Xiaoduiyou website code, UI, CSS, API implementation, deployment, database, Hermes/plugin wiring, or connector config from this public skill. Redact credentials/secrets as `[REDACTED]`.

## Route by task

| Task | Open |
|---|---|
| Poll turns, progress, callback/failure boundary | `references/runtime-turn-lifecycle.md` |
| Runtime API payloads/endpoints | `references/runtime-api-reference.md` |
| Content-package contract, `ui_templates`, `publish_notes`, process/result split | `references/content-package-contract.md` |
| Image upload and URL verification | `references/image-upload-contract.md` |
| Process document Markdown fidelity | `references/process-document-markdown.md` |
| Xiaohongshu / Moments publish tabs | `references/social-publish-result-template.md` |
| Product questions: Xiaohongshu + Taobao/Tmall + clickable cards | `references/product-question-workflow.md` |
| Travel planning workflow | `references/travel-plan-planning-workflow.md` |
| Travel Xiaohongshu reference images | `references/travel-plan-xhs-reference-workflow.md` |
| Travel result UI structured data | `references/travel-plan-result-template.md` |
| 成长日记 records/photos/summaries/enums | `references/growth-diary-agent.md` |

## Runtime rules

1. Use the Xiaoduiyou origin/auth context supplied by runtime.
2. Visible result pages render from structured `ui_templates` and `publish_notes`; process docs are evidence/editing surfaces.
3. Local/server-static paths are invalid in browser artifacts/docs/diary photos/message cards. Upload via `/api/assets`, use durable URLs, verify before callback.
4. Product questions: Xiaohongshu is experience/reference evidence; Taobao/Tmall is buyable/parameter evidence. Return clean clickable links and `image_attachments` cards when possible; for product-link cards, use the product page/listing's actual first product image, upload it to `/api/assets`/TOS first, then use the returned durable URL.
5. 成长日记: use `/api/growth-diary` and read live schema before writing.
6. Final callback: templates match data, publish tabs contain final copy/images only, process material stays in `source_markdown`/process blocks, images are durable, no secrets.

## Quick starts

### Social publish

- Select `ui_templates: ["xiaohongshu"]`, `["moments"]`, or both.
- Fill `publish_notes.xiaohongshu` and/or `publish_notes.moments`.
- Read `references/social-publish-result-template.md`.

### Product question / purchase research

- Search Xiaohongshu for lived experience; Taobao/Tmall for candidates/parameters.
- Clean links; upload rendered/source images through `/api/assets`; for Taobao/Tmall product cards, extract the actual first product image and upload that image, never a placeholder or hotlink.
- Return clickable `image_attachments`: `参考帖` for Xiaohongshu, `商品候选` for Taobao/Tmall.
- Put evidence in `source_markdown` or `product_research` if creating a document/artifact.
- Read `references/product-question-workflow.md` and `references/runtime-api-reference.md`.

### Travel plan

- Select `ui_templates: ["travel_plan"]`.
- Put data under `publish_notes.travel_plan.travel_plan`.
- Keep process material in `source_markdown` or `block_json`.
- Read `references/travel-plan-result-template.md` and `references/travel-plan-planning-workflow.md`.

### Growth diary

- `GET /api/growth-diary` first.
- `PATCH /api/growth-diary` for records, updates, deletions, field options, or view changes.
- Upload photos with `/api/assets` before writing attachment fields.
- Read `references/growth-diary-agent.md`.
