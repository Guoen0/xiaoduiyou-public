---
name: xiaoduiyou-growth-diary
description: "Xiaoduiyou Growth Diary workflow for records, photos, summaries, enum/schema-aware updates, and diary views. Use when the user mentions 成长日记, 宝宝记录, 喂养/睡眠/里程碑/照片入日记, family diary records, or asks to add/update/delete/query growth-diary data in Xiaoduiyou."
---

# Xiaoduiyou Growth Diary

Use this for immediately actionable Xiaoduiyou 成长日记 operations. Do not model diary records as content-package publish notes, and do not hide diary writes inside generic chat delivery.

## Trigger

Load this when the user asks to:

- Record, update, delete, or query 成长日记.
- Add baby photos/attachments to diary records.
- Summarize diary records or generate views/statistics from Xiaoduiyou diary data.
- Modify diary enum fields/options/views.

## Non-negotiables

1. Read live Growth Diary schema before writing.
2. Upload photos/assets via `/api/assets` before saving attachment fields.
3. Preserve enum option IDs/names from live schema; do not invent options unless the user explicitly asks to add them.
4. Deduplicate repeated real-world care events: same time + same event = one record with additional source/notes.
5. Keep family-care records in Feishu when the user is talking about the Feishu family log; use Xiaoduiyou Growth Diary only when the task is clearly Xiaoduiyou/Discord-side diary.

## Case map owned by Growth Diary

| User says / situation | Open/use | Why |
|---|---|---|
| `记录到成长日记` / `宝宝今天...` | `references/growth-diary-agent.md` | Diary records use `/api/growth-diary`. |
| `上传照片到成长日记` | `scripts/growth_diary_client.py upload` + `references/image-upload-contract.md` | Upload asset then write attachment field. |
| Growth diary schema/enums/views | `references/growth-diary-agent.md` | Must read live schema before writing. |
| Runtime auth/endpoints for diary calls | `references/runtime-api-reference.md` | Runtime conventions used by diary helper calls. |
| Query/summarize existing diary records | `references/growth-diary-agent.md` + `scripts/growth_diary_client.py get` | Use live records, then summarize. |

## Fast routing

| Need | Open |
|---|---|
| API and schema behavior | `references/growth-diary-agent.md` |
| Runtime endpoints/auth conventions | `references/runtime-api-reference.md` |
| Upload diary photos/assets | `references/image-upload-contract.md` |

## Scripts

- `scripts/growth_diary_client.py`: small CLI helper for authenticated GET/PATCH calls against `/api/growth-diary` and optional asset upload verification.

Quick use:

```bash
python ~/.hermes/skills/productivity/xiaoduiyou-growth-diary/scripts/growth_diary_client.py get
python ~/.hermes/skills/productivity/xiaoduiyou-growth-diary/scripts/growth_diary_client.py patch --payload /tmp/diary_patch.json
python ~/.hermes/skills/productivity/xiaoduiyou-growth-diary/scripts/growth_diary_client.py upload --session-id sess_0053 --file /tmp/photo.jpg
```
