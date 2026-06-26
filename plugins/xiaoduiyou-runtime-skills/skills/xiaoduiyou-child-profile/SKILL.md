---
name: xiaoduiyou-child-profile
description: "Xiaoduiyou child basic-profile workflow. Use when the user asks to view or update child basic info such as name, birthday, gender, allergy, height, weight, or child photo through chat."
---

# Xiaoduiyou Child Profile

Use this for immediately actionable Xiaoduiyou 孩子基础信息 operations from chat. This skill only owns the basic profile, not Growth Diary records and not development skill-tree progress.

## Trigger

Load this when the user asks to view or update:

- 宝宝/孩子名字、昵称、称呼
- 生日、出生日期
- 性别
- 过敏、疑似过敏、过敏体质
- 身高、体重
- 孩子照片/头像/相片 URL

If the user asks to log feeding/sleep/stool/symptom events, load `xiaoduiyou-growth-diary` instead. If the user asks to toggle development milestones or skill nodes, use the child page UI/state workflow, not this basic-profile tool.

## Non-Negotiables

1. Use first-class Xiaoduiyou connector tools: call `xiaoduiyou_child_get` before `xiaoduiyou_child_patch`.
2. The connector owns origin/auth. Do not search local files, env vars, browser cookies, config, or terminal history for `connection_token`.
3. Use the active turn's `agent_runtime_context` (`origin/base_url`, `home_id/family_id`, `session_id`, `sender`) as scope context only. Do not hard-code production, review, localhost, maintainer-specific URLs, or unrelated browser tabs.
4. Patch only fields the user explicitly provided. Do not overwrite unknown profile fields with defaults from examples.
5. Keep birthday as `YYYY-MM-DD` when possible. If the user gives an ambiguous date, ask one concise clarification before writing.
6. Store height in `heightCm` and weight in `weightKg` as strings, without unit text inside the value. Example: `80`, `10.5`.
7. For allergy, write a short factual note. Use empty string only when the user explicitly says to clear allergies.
8. For photos, pass only an HTTPS `photoUrl` that is already uploaded to Xiaoduiyou/TOS assets. Do not pass local paths, `file:`, `blob:`, localhost, or private-network URLs.
9. After patching, verify with `xiaoduiyou_child_get` and answer with the changed fields only.
10. Keep private family facts out of skill files. In local Hermes, durable household preferences belong in `${HERMES_HOME:-$HOME/.hermes}/private/xiaoduiyou-family-care-preferences.md`, not here.

## Fields

| User-facing field | Tool field |
|---|---|
| 名字 / 宝宝名字 / 昵称 | `profile.name` |
| 生日 / 出生日期 | `profile.birthday` |
| 性别 | `profile.gender` |
| 过敏 / 疑似过敏 | `profile.allergy` |
| 身高 | `profile.heightCm` |
| 体重 | `profile.weightKg` |
| 照片 / 相片 | `profile.photoUrl` |

## Tool Use

Read first:

```json
{}
```

Patch examples:

```json
{
  "profile": {
    "name": "宝宝",
    "birthday": "2025-04-20"
  }
}
```

```json
{
  "profile": {
    "heightCm": "81",
    "weightKg": "10.8",
    "allergy": "芒果嘴周易红"
  }
}
```

## Reply Style

Keep the confirmation short:

`已更新：名字 宝宝；生日 2025-04-20。`

If nothing was written because the message was ambiguous:

`生日我还不能确定是哪一天，请发 YYYY-MM-DD。`
