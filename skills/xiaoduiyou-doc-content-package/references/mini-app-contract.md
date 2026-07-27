# Xiaoduiyou mini-app contract

Use this contract whenever the user asks for an interactive page or mini app.

## Choose the mode

- Use `interactive_html` for a visually free, self-contained HTML/CSS/JS page whose state may reset.
- Use `mini_app` when user interactions must persist, synchronize inside one family, or survive reopening.
- Do not combine the modes to smuggle persistence into HTML. `interactive_html` has no storage or parent bridge.

For a stateful mini app, select `ui_templates: ["mini_app"]` and write
`fields.ui_payloads.mini_app`:

```json
{
  "schema": "xdy.mini_app.v1",
  "label": "去过的地方",
  "content": {
    "places": [
      { "id": "park", "name": "人民公园" },
      { "id": "museum", "name": "自然博物馆" }
    ]
  },
  "state_schema": {
    "visited": { "type": "string_set", "default": [] },
    "note": { "type": "string", "default": "" }
  },
  "view": {
    "type": "column",
    "children": [
      { "type": "text", "variant": "title", "value": "家庭打卡地图" },
      {
        "type": "list",
        "content_path": "places",
        "item": {
          "type": "checkbox",
          "state_path": "visited",
          "value": { "item_path": "id" },
          "label": { "item_path": "name" }
        }
      },
      { "type": "text_input", "state_path": "note", "label": "备注" }
    ]
  }
}
```

## Fixed vocabulary

State types:

- `string`
- `number`
- `boolean`
- `string_set`
- `string_list`

View nodes:

- Layout: `column`, `row`, `grid`, `card`
- Display: `text`, `image`, `tag`, `progress`
- Input: `checkbox`, `text_input`, `number_input`, `select`
- Data: `list`
- Action: `button`

Actions:

- `set`
- `toggle`
- `increment`
- `toggle_set`
- `append`
- `remove`
- `move`

Expressions may read only `content_path`, `state_path`, or a list item's
`item_path`. There is no JavaScript event handler, SDK, parent bridge, or
`data-xdy-action` contract.

## Buttons and actions

`button.action` is always an object. Never write an action as a bare string
such as `"action": "set"`.

```json
{
  "type": "button",
  "label": "清空备注",
  "action": {
    "type": "set",
    "path": "note",
    "value": ""
  }
}
```

The action `path` must name a field declared in `state_schema`. Most input
nodes already save automatically, so do not add a “保存” button to a
`checkbox`, `text_input`, `number_input`, or `select` unless the button performs
a separate valid action.

When the document tool returns `INVALID_MINI_APP_DEFINITION`, read all returned
fields before retrying:

- `capability_available: true` means mini-app support is active; the submitted
  definition is invalid.
- `path` is the exact invalid JSON location.
- `reason` explains the violated rule.
- `expected` is a minimal valid shape or vocabulary.
- `skill_reference` points back to this installed Skill and reference file.

Correct only the invalid definition and retry. Never infer that the platform
does not support mini apps from this validation error.

## Author updates

The author updates `content`, `state_schema`, and `view` through the normal
document update tool. After a successful update, the server immediately cleans
every family's state against the new schema:

- Same name and same type: preserve the value.
- Removed field: delete it.
- Changed type: reset it to the new default.

Do not write migrations. Invalid definitions are rejected with
`INVALID_MINI_APP_DEFINITION`.

## Sharing behavior

- Members of the author's family share one server-side state.
- Another family may collect the public mini app. It follows the author's latest
  definition but owns separate family state.
- Guests keep structured mini-app state only in the current browser until they
  sign in and collect it.
- `interactive_html` remains stateless in every sharing mode.
