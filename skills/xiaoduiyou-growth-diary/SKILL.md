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
3. When a diary write records height, weight, allergy, suspected allergy, or allergy constitution, also sync the child basic profile: after the diary write, call `xiaoduiyou_child_get`, then `xiaoduiyou_child_patch` with only the provided `profile.heightCm`, `profile.weightKg`, and/or `profile.allergy`, then verify with `xiaoduiyou_child_get`. Keep the diary record as history; child profile stores the current basic-info value.
4. Use the active turn's `agent_runtime_context` (`origin/base_url`, `home_id/family_id`, `session_id`, `surface`, `sender`) as scope context only. Do not hard-code production, review, localhost, maintainer-specific domains, or URLs copied from an unrelated browser tab/local config.
5. If connector diary tools are unavailable or `agent_runtime_context.origin` is absent/unusable, ask for reconnection/target environment and family/home scope instead of guessing.
6. Upload photos/assets via connector-supported `/api/assets` tooling before saving attachment fields.
7. Preserve enum option IDs/names from live schema; do not invent options unless the user explicitly asks to add them.
8. Deduplicate repeated real-world care events: same time + same event = one record with additional source/notes.
9. Always set `recorder` for message-derived records from the active Xiaoduiyou sender `display_name` (for example `大笨钟` or `金心`) and preserve the raw user wording in `original_message`; do not default human-reported events to `臭宝机器人` or omit the recorder when sender context is present.
10. For event time, use the user's message time as the fallback source of truth. If the user states an explicit date/time for that specific event, use that. If the user says "now", "刚才", or gives no time, derive `occurred_at` and `date` from the active Xiaoduiyou turn/user-message `created_at` timestamp. Example: `12:20 吃馒头` records food at 12:20; a later bare `喝奶 180` records at the message send time, not 12:20. Do not carry a previously mentioned clock time forward to later events unless the user explicitly ties that later event to the same time. If a prior unlogged message needs recording/correction, look up that message's timestamp from session/gateway context when available and write it directly; do not ask the caregiver to remember, resend, or restate the time. Agent writes must send `date` as `YYYY-MM-DD` and `occurred_at` as `YYYY-MM-DD HH:mm:ss` with matching dates; short times like `19:20` are invalid and will be rejected. Do not invent clock times, round to arbitrary times, or use the Agent's local/system time unless that time is the Xiaoduiyou-provided turn timestamp.
11. Keep family-care records in Feishu when the user is talking about the Feishu family log; use Xiaoduiyou Growth Diary only when the task is clearly Xiaoduiyou/Discord-side diary.
12. Keep private family context out of skill files. In a local Hermes environment, read or create `${HERMES_HOME:-$HOME/.hermes}/private/xiaoduiyou-family-care-preferences.md` for family-specific names, Feishu IDs, caregiver mappings, childcare preferences, and durable care-history facts. Update that file when the user gives durable private preferences; keep reusable diary behavior in this skill. This path is outside `skills/` and `plugins/` so skill upgrades should not overwrite it.

## Case map owned by Growth Diary

| User says / situation | Open/use | Why |
|---|---|---|
| `记录到成长日记` / `宝宝今天...` | `references/growth-diary-agent.md` | Diary records use `/api/growth-diary`. |
| `上传照片到成长日记` | First-class connector asset/tool support when available + `references/image-upload-contract.md` | Upload asset first, then write attachment field. Do not discover tokens manually. |
| Growth diary schema/enums/views | `references/growth-diary-agent.md` | Must read live schema with `xiaoduiyou_growth_diary_get` before writing. |
| Runtime auth/endpoints for diary calls | `references/runtime-api-reference.md` | Runtime conventions used by diary helper calls. |
| Query/summarize existing diary records | `references/growth-diary-agent.md` + `xiaoduiyou_growth_diary_get` | Use live connector-owned records, then summarize. |
| 身高/体重/过敏记录 | `references/growth-diary-agent.md` + `xiaoduiyou_child_get` / `xiaoduiyou_child_patch` | Write diary history and sync latest child basic profile fields. |

## Fast routing

| Need | Open |
|---|---|
| API and schema behavior | `references/growth-diary-agent.md` |
| Runtime endpoints/auth conventions | `references/runtime-api-reference.md` |
| Upload diary photos/assets | `references/image-upload-contract.md` |

## Tool use

- Xiaoduiyou Growth Diary operating knowledge belongs in this skill, not Hermes memory. When the user corrects diary behavior or a caregiver shorthand is learned, patch this skill so future Xiaoduiyou agents share the same behavior.
- Primary path: `xiaoduiyou_growth_diary_get` before every write, then `xiaoduiyou_growth_diary_patch` for mutations.
- Use `date`, `start_date`/`end_date`, and/or `record_limit` on reads whenever the user gives a target date/range.
- After a write, verify with a filtered `xiaoduiyou_growth_diary_get` keyed by the new record's date/type/query/quantity. The PATCH response is intentionally concise and may include unrelated sample/legacy `created_records` rows in its summary; do not rely on that summary alone to confirm the exact newly saved event.
- For edits to an existing record, use `updates` as one item per field: `{table_id, record_id, field_id, value}`. Do **not** send an update object with `values: {...}`; that shape is only for new `records` and can fail with `COLUMN_NOT_FOUND`.
- When correcting a recently logged no-time event, identify the exact record by date/event/title/source first, then set `occurred_at` to the original Xiaoduiyou message timestamp (or the existing record `created_at` converted to local event time if that is the only connector-visible trace), not the page date and not the Agent runtime clock.
- Decide create vs update by real-world event time, not by event type alone. For a new caregiver message with no explicit correction wording, compare its `occurred_at` or message-send time with the nearest same-type record on that date: within 10 minutes can be treated as a likely correction/supplement to that event; 10-30 minutes is ambiguous and should only update when the wording clearly points back to the earlier event, otherwise create; more than 30 minutes means create a new diary record by default. A later `喝奶 180`, `拉屎一次`, `吃饭`, `加锌`, etc. is usually a new care event, even when the quantity/content matches an earlier row.
- If the user says the current visible context is missing earlier messages in the same Xiaoduiyou `session_id`, assume the gateway agent context may have been refreshed/evicted. Check `session_search(session_id=...)` when you know the Hermes session id; otherwise search `~/.hermes/logs/agent.log` for the Xiaoduiyou `sess_*`, key phrases, `history=0`, and `Agent cache idle-TTL evict`. Use the original inbound message timestamp as the event time when the user explicitly asks for "the time that message was received." Do not treat a later `history=0` turn in the same Xiaoduiyou session as the original event time without checking for older log/session entries.
- Current screen/page date is UI context only. The user may be viewing a different date/page; never let visible page date override explicit user time/date or Xiaoduiyou message-send time.
- Caregiver shorthand: for `锌` / `加锌` with a bare number (e.g. `锌 1`, `加锌2`), interpret the number as milliliters and save `unit: "ml"`, title/content like `锌 1ml`, unless the user explicitly states another unit.
- Caregiver time shorthand: if the user gives a broad daypart as the event time (e.g. `中午拉屎也一次`), treat it as an explicit coarse time rather than asking again. Use the conventional anchor for that daypart (`中午` -> `12:00:00`, `晚上` -> `20:00:00`) on the active diary date, preserve the raw wording in `original_message`, and make the content clear that it was a daypart report (e.g. `中午拉屎一次。`).
- Height, weight, and allergy diary writes are dual-write records. First write/verify the diary event, then sync the latest child profile fields with `xiaoduiyou_child_get` and `xiaoduiyou_child_patch`. Store height as `profile.heightCm` and weight as `profile.weightKg` strings without unit text (for example `85`, `11.2`). Store allergy as a concise factual note (for example `芒果嘴周易红`); clear it only when the user explicitly says there is no allergy or asks to clear it. Do not overwrite unrelated profile fields.
- For totally time-less caregiver event messages like bare `拉屎一次` / `喝奶 180`, default to the Xiaoduiyou message-send time as the event time. Treat caregiver shorthand with no explicit date/time as “now / when this message was sent”; do not ask for a time. If the connector/runtime prompt does not expose an exact `created_at`, do not discard the event; use available conversation context, adjacent turn timing, or the caregiver's later correction to save the closest reasonable message-send time, and be explicit only if precision is approximate.
- If the caregiver clarifies `现在喝的奶` / `现在这顿` / `当前这次`, treat it as a new current-time event unless they explicitly say it is a correction to an earlier row. Never overwrite or move the previous visible milk/feed record just because the new current event has the same quantity.
- Repeated caregiver feeding/care messages are usually repeated real events, not duplicates: if the caregiver sends `喝奶 180` multiple times at different message times, create one record per message using each message-send time. Only treat it as a duplicate when the same event has the same time (explicit or message timestamp) and same quantity/content.
- Apply practical caregiver-context sanity checks before writing, but do not turn normal variation into interrogation. Use common sense to silently proceed when an event is plausible even if it is not a textbook schedule. Only interrupt the caregiver when there is a clear, high-impact conflict or likely typo/date mistake (e.g. two large milk feeds extremely close together on the same date, impossible units/quantities, medication/fever safety risk, or a record that would duplicate/conflict with an existing nearby event). Prefer making a context-based correction when confidence is high; ask one concise confirmation only when the ambiguity cannot be resolved safely.
- Voice-note diary input: transcribe before writing, then preserve the interpreted raw wording in `original_message`. On macOS Apple Silicon, check/use `mlx_whisper` first when available; then fall back to configured Hermes STT / `faster-whisper` / existing Whisper installs. Do not install a new Whisper package before checking `mlx_whisper` and already-installed STT options. For short caregiver audio with noisy recognition, compare more than one local transcription when cheap and use childcare context to normalize obvious ASR confusions (e.g. `吸的/稀的` in a stool report), but keep the saved wording conservative and factual.
- For voice attachments that are meant to become diary records, transcribe first, then apply the same event-time and dedupe rules as text. On local macOS/Apple Silicon environments, check/use an existing `mlx_whisper` installation before generic Whisper/faster-whisper/openai-whisper, and do not install STT packages unless no suitable local transcriber is available. For local transcription fallback, keep the transcript in `original_message` as `语音：...`.
- Do not use local scripts, browser cookies, config files, terminal history, or connection-token discovery for connected-agent diary I/O. If the connector tools are unavailable, stop and ask for reconnection/target scope.

## Care Record Semantics

Use these rules for high-frequency baby-care records such as milk, meals, water, supplements, stool, sleep, outings, symptoms, height/weight, photos, notes, and daily summaries.

- Before relying on family-specific record surfaces, caregiver mappings, Feishu IDs, or household logging preferences, check `${HERMES_HOME:-$HOME/.hermes}/private/xiaoduiyou-family-care-preferences.md` when running in local Hermes. If it is missing and the user provides durable private context, create it there instead of adding that data to this skill.
- Keep records traceable: preserve raw caregiver wording in `original_message`; clean the title/content for readability; set `recorder` from the active sender when available.
- Normalize obvious shorthand instead of asking the caregiver to rephrase. Examples: bare milk amounts mean `ml`; `喝奶-90` means `喝奶 90ml`; `拉屎/拉臭/大便` means stool; Chinese count words like `一次/两次` should become numeric quantities when the schema supports it.
- For milk without an amount, only default an amount when there is a stable family convention or nearby context. Otherwise record the event without inventing quantity.
- Treat additives given with milk as part of the milk record when the wording is one combined event, for example `喝奶 180，加锌 1.5ml`; do not split into a separate supplement record unless the user clearly reports a separate supplement event.
- If a caregiver sends a new milk message with the same quantity as an earlier same-day record but adds an additive/supplement (e.g. earlier `喝奶180ml`, later `喝奶180ml 加2ml锌`), default to a new event at the current message time. Do not retrofit the earlier record unless the caregiver explicitly says it was a correction to that earlier feed (e.g. “刚才那次补充加锌”). If you incorrectly merged it and the caregiver says “是现在/不是那次”, restore the older record and create a separate current-time record.
- If the caregiver gives content first and says the time will come later, hold it in the current conversation instead of creating a guessed-time row. When the time arrives, create one record and preserve both messages in `original_message`.
- If the user sends a late-night correction after midnight with wording like `昨晚`, `晚上那顿`, or an obvious prior-evening reference, map it to the previous calendar date and verify `date` plus `occurred_at`.
- For coarse time-of-day stool records such as `中午拉屎`, do not ask for exact time. Use a representative time only if the product/schema requires a timestamp, and state in content that exact time/character was not specified.
- Corrections update the existing real-world event instead of creating duplicates. Duplicate reports from multiple caregivers for the same event should merge into one record, preserving useful source wording.
- Do not rewrite an older same-day record just because it is the nearest or most similar record. The default scale for ordinary care events is: same exact event/time = merge; very near in time = possible correction; meaningfully later = new record. Treat explicit correction language such as `刚才那次改成...`, `上一条不对`, `补充刚刚那顿`, `不是180是160`, or `把那条改一下` as update intent. Treat current-event language or bare new event messages such as `现在喝的奶`, `又拉了一次`, `喝奶180`, `加锌1ml`, or `吃了半碗` as create intent unless the time is within the near-correction window.
- Corrections to height, weight, or allergy should update the corresponding diary record and sync the child profile when the corrected value is the latest known basic-info value.
- Photos can support descriptions of visible features, but do not diagnose from images alone. Pair photo-based notes with observable markers and red flags.

## Risk, Advice, And Summaries

- Ordinary meals, milk, water, sleep, and normal stool should stay low-noise: normal risk, brief factual content, and no alarmist advice.
- Use observation/advice/red-flag levels only for meaningful concerns: blood/black stool, repeated watery stool with poor energy/low urine/dry lips, persistent high fever, frequent vomiting, allergy signs, medication ambiguity, falls/burns/ingestion, eye-area swelling with persistent rubbing, or other clear safety issues.
- Advice should be concise, practical, non-diagnostic, and visible to caregivers when it affects shared care. Mention concrete observable markers such as energy, urine, hydration, fever, blood, repeated watery stool, pain, rash, swelling, or breathing.
- For daily summaries, merge and de-duplicate instead of listing every raw event. Prefer two user-facing parts when the schema/content allows it: `汇总评估` for factual assessment and `明日建议` for monitoring/action guidance.
- When summarizing symptoms or medical-like histories, keep a structured case frame: timeline, feeds/foods, medications, labs if provided, response to interventions, facts versus inferences, leading explanation, aggravating factors, and red flags that require medical care.
