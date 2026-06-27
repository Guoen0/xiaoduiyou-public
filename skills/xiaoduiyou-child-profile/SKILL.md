---
name: xiaoduiyou-child-profile
description: "Xiaoduiyou child profile and development-progress workflow. Use when the user asks to view or update child basic info such as name, birthday, gender, allergy, height, weight, photo, or the four development skill-node dimensions through chat."
---

# Xiaoduiyou Child Profile

Use this for immediately actionable Xiaoduiyou 孩子基础信息 and 发育进度 skill-node operations from chat. This skill owns the current child profile plus the four development dimensions' lit/unlit skill-node state. It does not own Growth Diary records.

## Trigger

Load this when the user asks to view or update:

- 宝宝/孩子名字、昵称、称呼
- 生日、出生日期
- 性别
- 过敏、疑似过敏、过敏体质
- 身高、体重
- 孩子照片/头像/相片 URL
- 发育进度、四个维度、技能点、计量点、点亮/熄灭、已掌握/未掌握
- 大运动、精细动作、语言认知、社交自理

If the user asks to log feeding/sleep/stool/symptom events, load `xiaoduiyou-growth-diary` instead. Growth Diary may still call this profile tool after diary writes for height, weight, allergy, suspected allergy, or allergy constitution so the current child basic-info fields stay in sync.

## Non-Negotiables

1. Use first-class Xiaoduiyou connector tools: call `xiaoduiyou_child_get` before `xiaoduiyou_child_patch`.
2. The connector owns origin/auth. Do not search local files, env vars, browser cookies, config, or terminal history for `connection_token`.
3. Use the active turn's `agent_runtime_context` (`origin/base_url`, `home_id/family_id`, `session_id`, `sender`) as scope context only. Do not hard-code production, review, localhost, maintainer-specific URLs, or unrelated browser tabs.
4. Patch only fields or skill nodes the user explicitly provided. Do not overwrite unknown profile fields or unrelated skill-node states with defaults from examples.
5. Keep birthday as `YYYY-MM-DD` when possible. If the user gives an ambiguous date, ask one concise clarification before writing.
6. Store height in `heightCm` and weight in `weightKg` as strings, without unit text inside the value. Example: `80`, `10.5`.
7. For allergy, write a short factual note. Use empty string only when the user explicitly says to clear allergies.
8. For photos, pass only an HTTPS `photoUrl` that is already uploaded to Xiaoduiyou/TOS assets. Do not pass local paths, `file:`, `blob:`, localhost, or private-network URLs.
9. For development progress, read `development[].nodes[]` from `xiaoduiyou_child_get`. Patch `skill_node_states` using the exact node `key` returned there, with `true` for lit/unlocked and `false` for unlit/locked. Do not invent keys from memory.
10. After patching, verify with `xiaoduiyou_child_get` and answer with the changed fields/nodes only.
11. Keep private family facts out of skill files. In local Hermes, durable household preferences belong in `${HERMES_HOME:-$HOME/.hermes}/private/xiaoduiyou-family-care-preferences.md`, not here.
12. When called from `xiaoduiyou-growth-diary` after a height/weight/allergy diary record, patch only the latest provided `heightCm`, `weightKg`, and/or `allergy`; the diary record remains the historical source of the event.

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

## Development Fields

`xiaoduiyou_child_get` returns:

- `development[].id`: `grossMotor`, `fineMotor`, `languageCognition`, `socialEmotion`
- `development[].name`: 大运动、精细动作、语言认知、社交自理
- `development[].litCount` / `totalCount`
- `development[].nodes[]`: `{ key, name, age, lit }`

Patch development nodes with:

```json
{
  "skill_node_states": {
    "grossMotor:独走几步": true,
    "languageCognition:听懂一步指令": false
  }
}
```

Use this when the user says a skill is now mastered, not yet mastered, 点亮, 熄灭, 已掌握, 未掌握, or asks you to update the current 发育进度. For analysis-only requests, call `xiaoduiyou_child_get` and use `development` without patching.

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
  "skill_node_states": {
    "socialEmotion:指给大人看": true
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
