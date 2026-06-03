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
2. Use first-class Xiaoduiyou connector tools for diary I/O: `xiaoduiyou_growth_diary_get` before writes, then `xiaoduiyou_growth_diary_patch` for mutations. When the user gives a target date/range, pass `date`, `start_date`/`end_date`, and/or `record_limit` to `xiaoduiyou_growth_diary_get` so the connector returns live schema plus only relevant records instead of the full table. The connector owns origin/auth; the model must not search local files, env vars, config, browser cookies, or terminal history for `connection_token`.
3. Use the active turn's `agent_runtime_context` (`origin/base_url`, `home_id/family_id`, `session_id`, `surface`, `sender`) as scope context only. Do not hard-code production, review, localhost, maintainer-specific domains, or URLs copied from an unrelated browser tab/local config.
4. If connector diary tools are unavailable or `agent_runtime_context.origin` is absent/unusable, ask for reconnection/target environment and family/home scope instead of guessing.
5. Upload photos/assets via connector-supported `/api/assets` tooling before saving attachment fields.
6. Preserve enum option IDs/names from live schema; do not invent options unless the user explicitly asks to add them.
7. Deduplicate repeated real-world care events: same time + same event = one record with additional source/notes.
8. Keep family-care records in Feishu when the user is talking about the Feishu family log; use Xiaoduiyou Growth Diary only when the task is clearly Xiaoduiyou/Discord-side diary.

## Case map owned by Growth Diary

| User says / situation | Open/use | Why |
|---|---|---|
| `记录到成长日记` / `宝宝今天...` | `references/growth-diary-agent.md` | Diary records use `/api/growth-diary`. |
| `上传照片到成长日记` | First-class connector asset/tool support when available + `references/image-upload-contract.md` | Upload asset first, then write attachment field. Do not discover tokens manually. |
| Growth diary schema/enums/views | `references/growth-diary-agent.md` | Must read live schema with `xiaoduiyou_growth_diary_get` before writing. |
| Runtime auth/endpoints for diary calls | `references/runtime-api-reference.md` | Runtime conventions used by diary helper calls. |
| Query/summarize existing diary records | `references/growth-diary-agent.md` + `xiaoduiyou_growth_diary_get` | Use live connector-owned records, then summarize. |

## Fast routing

| Need | Open |
|---|---|
| API and schema behavior | `references/growth-diary-agent.md` |
| Runtime endpoints/auth conventions | `references/runtime-api-reference.md` |
| Upload diary photos/assets | `references/image-upload-contract.md` |

## Tool use

- Primary path: `xiaoduiyou_growth_diary_get` before every write, then `xiaoduiyou_growth_diary_patch` for mutations.
- Use `date`, `start_date`/`end_date`, and/or `record_limit` on reads whenever the user gives a target date/range.
- Do not use local scripts, browser cookies, config files, terminal history, or connection-token discovery for connected-agent diary I/O. If the connector tools are unavailable, stop and ask for reconnection/target scope.
