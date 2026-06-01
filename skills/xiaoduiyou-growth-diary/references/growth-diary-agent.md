# Xiaoduiyou Growth Diary Agent Contract

This reference is bundled inside `xiaoduiyou-growth-diary`. Use it when a connected Agent needs to operate Xiaoduiyou 成长日记 through runtime APIs. It documents the public runtime contract only: no source-code edits, no deployment steps, no private database surgery, and no credentials.

## When to use

Use this reference when the user asks the Agent to:

- record a baby/care event into 成长日记;
- edit or correct an existing growth-diary record;
- upload photos/attachments for a growth-diary record;
- add a new colored enum option for an editable select field;
- delete an incorrect growth-diary record after explicit user intent.

Do not use this for website/API implementation work. Product code changes must be handled through Xiaoduiyou development/maintenance, not this runtime usage package.

## API surface

Use the Xiaoduiyou origin and auth context supplied by the connected runtime.

### Read current schema and records

```http
GET /api/growth-diary
```

Response:

```json
{
  "base": {
    "base_id": "growth_<home_id>",
    "home_id": "...",
    "name": "成长日记",
    "tables": [
      {
        "table_id": "tbl_growth_events",
        "name": "成长事件",
        "fields": [],
        "records": [],
        "views": [],
        "active_view_id": "view_calendar_timeline"
      }
    ]
  }
}
```

Always read first. Treat `fields` as the source of truth for option ids, labels, colors, and field types.

### Patch records, options, and views

```http
PATCH /api/growth-diary
Content-Type: application/json
```

Body shape:

```ts
type GrowthDiaryPatchRequest = {
  records?: Array<{ table_id?: string; source?: 'agent' | 'manual' | 'feishu' | 'system'; values?: Record<string, unknown> }>;
  updates?: Array<{ table_id?: string; record_id?: string; field_id?: string; value?: unknown }>;
  deletions?: Array<{ table_id?: string; record_id?: string }>;
  field_options?: Array<{ table_id?: string; field_id?: string; label?: string; color?: string }>;
  views?: Array<{ view_id?: string; table_id?: string; name?: string; type?: string; visible_field_ids?: string[] }>;
};
```

Success returns `{ "base": ... }` with the updated base. Errors return status `400` and one of:

- `TABLE_NOT_FOUND`
- `ROW_NOT_FOUND`
- `COLUMN_NOT_FOUND`
- `INVALID_VIEW`
- `BAD_JSON`

## Canonical table and fields

Default table id: `tbl_growth_events`.

Important fields:

| field_id | Type | Notes |
|---|---|---|
| `date` | date | `YYYY-MM-DD`; auto-filled from `occurred_at` for new records if omitted. |
| `occurred_at` | datetime | Prefer `YYYY-MM-DD HH:mm:ss`. |
| `event_type` | single_select | Store option id when known; labels also normalize through aliases. |
| `title` | text | Required in UI; for Agent writes may be derived from `content` if omitted. |
| `content` | long_text | Structured short description. |
| `quantity` | number | Use numeric strings or numbers; leave blank/null if not applicable. |
| `unit` | single_select | Use option id from schema. Current labels include `ml`, `kg`, `cm`, `次`, `克`, `碗`, `滴`, `袋`, `粒`, `小时`, `分钟`, `少量`, `适量`, `较多`. |
| `risk` | single_select | Current labels: `正常`, `需观察`, `建议处理`, `红旗提醒`. Defaults to `正常`. Use canonical id `need_watch` for `需观察`. |
| `tags` | multi_select | Use option ids or labels; current labels include stool traits, `新食物`, mood, appetite, skin tags, and symptom tags. |
| `photos` | attachment | Array of uploaded asset metadata. |
| `advice` | long_text | Short advice/analysis for ordinary event rows only. For `每日汇总`, leave this empty; put all group-facing summary/advice in `content`. |
| `original_message` | long_text | Preserve user wording or source text for message-derived event rows. For scheduled `每日汇总`, leave this empty. |
| `recorder` | text | Human or Agent recorder, e.g. `大笨钟`, `金心`, `臭宝机器人`. |

## Current enum labels

Read live schema before writing, but these are the expected defaults.

### event_type

- `🍼 奶`
- `🥣 吃饭`
- `💩 拉臭` — color is brown
- `💧 饮水`
- `💊 用药/补剂`
- `📏 身高`
- `⚖️ 体重`
- `😴 睡眠`
- `🚼 外出`
- `🤒 症状`
- `每日汇总` — color is black
- `👶 备注`

### unit

- `ml`, `kg`, `cm`
- `次`, `克`, `碗`
- `滴`, `袋`, `粒`
- `小时`, `分钟`
- `少量`, `适量`, `较多`

### risk

- `正常` → `normal`
- `需观察` → `need_watch`
- `建议处理` → `action`
- `红旗提醒` → `red_flag`

### tags / 性状标签

- 大便性状：`正常`, `偏稀`, `水样`, `偏硬`, `量少`, `量多`
- `新食物`
- 心情/精神：`精神好`, `烦躁`, `精神差`, `哭闹`
- 食欲：`食欲好`, `食欲一般`
- 皮肤：`皮疹`, `红肿`, `破皮`, `蚊虫包`, `淤青`, `肿胀`
- 症状：`发热`, `昏迷`, `呕吐`

## Daily summary records

`每日汇总` is normally scheduled/system-triggered, not copied from one raw user message. When creating or updating a daily summary:

- Use `event_type: "summary"` / `每日汇总` and a title like `YYYY-MM-DD 每日汇总`.
- Leave `original_message` empty.
- Leave `advice` empty to avoid duplicating the summary in two fields.
- Put all group-facing text in `content` only.
- Use exactly these section headers in `content`: `【汇总评估】` and `【明日建议】`. Do not add `【群内简报】` or `【计量评估】`.
- Make the summary concise and readable for a family group chat.
- Combine same-day measurements with the child stage and recent trend from previous days: e.g. milk amount too high/low, stool count improving/worsening, missing sleep/water records, skin/symptom changes.
- Give practical tomorrow guidance, including what to keep, what to reduce/increase, what to record, and red-flag symptoms when relevant.

Example:

```json
{
  "records": [
    {
      "table_id": "tbl_growth_events",
      "source": "system",
      "values": {
        "date": "2026-05-21",
        "occurred_at": "2026-05-21 23:59:00",
        "event_type": "summary",
        "title": "2026-05-21 每日汇总",
        "content": "【汇总评估】今天明显转稳：排便1次，较前几天3–4次改善；三餐节奏正常，奶约320ml略少，饮水和睡眠缺记录。整体可按正常观察。\n【明日建议】继续三餐规律，奶量尽量补到400ml以上或确认其他乳制品；补记饮水、睡眠和大便性状，观察排便、精神和食欲是否稳定。",
        "risk": "normal",
        "original_message": "",
        "advice": "",
        "recorder": "臭宝机器人"
      }
    }
  ]
}
```

## Create a record

Minimal Agent-created record:

```json
{
  "records": [
    {
      "table_id": "tbl_growth_events",
      "source": "agent",
      "values": {
        "occurred_at": "2026-05-23 12:30:00",
        "event_type": "food",
        "content": "午饭吃面 30 克，食欲一般。",
        "quantity": 30,
        "unit": "grams_cn",
        "risk": "normal",
        "tags": "食欲一般",
        "recorder": "臭宝机器人",
        "original_message": "12:30 吃面 30g"
      }
    }
  ]
}
```

Notes:

- Set `source: "agent"` for Agent-created rows.
- If `date` is omitted, runtime derives it from `occurred_at`.
- If `title` is omitted, runtime derives it from `content`.
- Prefer option ids from the live schema. Labels are accepted for common aliases, but ids are safer.
- Do not invent enum labels. If a needed value is missing, either add a colored option through `field_options` after user intent, or leave the field blank when no true schema value exists.

## Edit a record

1. `GET /api/growth-diary`.
2. Find the exact `record_id` by date/time/title/source.
3. Patch only fields that need changing.

```json
{
  "updates": [
    {
      "table_id": "tbl_growth_events",
      "record_id": "agent_xxx",
      "field_id": "risk",
      "value": "need_watch"
    },
    {
      "table_id": "tbl_growth_events",
      "record_id": "agent_xxx",
      "field_id": "tags",
      "value": "偏稀，烦躁"
    }
  ]
}
```

## Delete a record

Only delete when the user explicitly asks or the task clearly says to remove an erroneous record.

```json
{
  "deletions": [
    { "table_id": "tbl_growth_events", "record_id": "agent_xxx" }
  ]
}
```

## Add a colored enum option

Use this only when the existing schema lacks a needed option and the user wants it captured as structured data.

```json
{
  "field_options": [
    { "table_id": "tbl_growth_events", "field_id": "tags", "label": "过敏疑似", "color": "rose" }
  ]
}
```

Allowed colors include: `slate`, `gray`, `zinc`, `red`, `rose`, `orange`, `amber`, `yellow`, `lime`, `green`, `emerald`, `teal`, `cyan`, `sky`, `blue`, `indigo`, `violet`, `purple`, `fuchsia`, `pink`, `brown`, `black`.

## Upload photos for a record

Local file paths are never valid browser URLs. Upload first through Xiaoduiyou assets, then reference returned asset metadata in `photos`.

```http
POST /api/assets
Content-Type: multipart/form-data
```

Recommended multipart fields:

- `file`: image file
- `source`: `agent_generated` or another runtime-supported source
- `require_remote_storage`: `true`

Then create or edit the record with:

```json
{
  "updates": [
    {
      "table_id": "tbl_growth_events",
      "record_id": "agent_xxx",
      "field_id": "photos",
      "value": [
        {
          "asset_id": "asset_xxx",
          "url": "https://...",
          "mime_type": "image/jpeg",
          "name": "photo.jpg",
          "width": 1200,
          "height": 1600
        }
      ]
    }
  ]
}
```

For new records, put the same array under `values.photos`.

## Validation checklist

Before final user-facing reply:

- [ ] Read live schema first and used `tbl_growth_events` unless the live table differs.
- [ ] Used `source: "agent"` for Agent-created records.
- [ ] Preserved user/source wording in `original_message` when available; left it empty for scheduled `每日汇总`.
- [ ] For `每日汇总`, left `advice` empty and put concise `【汇总评估】` / `【明日建议】` text in `content`.
- [ ] Set `recorder` when known.
- [ ] Used live enum option ids or known labels; did not invent uncolored enums silently.
- [ ] Uploaded local images to `/api/assets` and used returned browser-accessible URLs.
- [ ] Re-read `GET /api/growth-diary` or checked PATCH response to verify the record exists/changed.
- [ ] Reported concise outcome: created/edited/deleted, time, title, and any caveat.
