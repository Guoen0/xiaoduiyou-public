# Xiaoduiyou Usage Skill

This is the **single public Xiaoduiyou skill package** for connected Agents. Download `xiaoduiyou-usage-workflow.zip`, unzip it, and keep `SKILL.md` and `references/` together.

For Hermes Agent, recommended layout:

```text
~/.hermes/skills/productivity/xiaoduiyou-usage-workflow/
  SKILL.md
  README.md
  references/
    runtime-turn-lifecycle.md
    content-package-contract.md
    growth-diary-agent.md
    image-upload-contract.md
    process-document-markdown.md
    social-publish-result-template.md
    travel-plan-planning-workflow.md
    travel-plan-xhs-reference-workflow.md
    travel-plan-result-template.md
```

Other Agent runtimes can place the folder wherever their skill loader expects.

## Start here

1. Read `SKILL.md` first. It defines boundaries, turn lifecycle, result/process split, image rules, and the final validation checklist.
2. Use the reference file that matches the requested surface:

| User/task surface | Reference |
|---|---|
| Runtime turn polling/progress/callback boundary | `references/runtime-turn-lifecycle.md` |
| General content-package contract, templates, process/result split | `references/content-package-contract.md` |
| 成长日记 records, photos, daily summaries, enum options | `references/growth-diary-agent.md` |
| Xiaohongshu / Moments publish tabs | `references/social-publish-result-template.md` |
| Travel planning workflow + process document + quality constraints | `references/travel-plan-planning-workflow.md` |
| Xiaohongshu travel reference images | `references/travel-plan-xhs-reference-workflow.md` |
| Travel-plan result UI | `references/travel-plan-result-template.md` |
| Generated/local image uploads | `references/image-upload-contract.md` |
| Markdown/table fidelity in process docs | `references/process-document-markdown.md` |

## Quick rules

- Do not change Xiaoduiyou source code, deployment, database, or Agent connector configuration from this public usage skill.
- Visible result pages render from structured `ui_templates` and `publish_notes`; process docs are for evidence and editing.
- Upload local/generated images to `/api/assets` before using them in artifacts, documents, or growth-diary photos.
- For 成长日记, use `/api/growth-diary` and the bundled Growth Diary reference; do not model diary entries as content-package publish tabs.
