# Xiaoduiyou Mini App V2 authoring contract

Use this reference whenever a user asks for a Xiaoduiyou interactive page or mini app.

V2 is the only accepted structured mini-app schema. Emit `xdy.mini_app.v2`.
Never emit or retry with `xdy.mini_app.v1`.

## Contents

- [Authoring workflow](#authoring-workflow)
- [Choose the mode](#choose-the-mode)
- [Document payload](#document-payload)
- [V2 payload and vocabulary](#v2-payload-and-vocabulary)
- [Manifest and capabilities](#manifest-and-capabilities)
- [Data, state, and scopes](#data-state-and-scopes)
- [Expressions and computed values](#expressions-and-computed-values)
- [Actions](#actions)
- [Pages and components](#pages-and-components)
- [Collection browser](#collection-browser)
- [Platform resources](#platform-resources)
- [Updates, sharing, and limits](#updates-sharing-and-limits)
- [Validation failures](#validation-failures)

## Authoring workflow

1. Read this file completely.
2. When the tool is available, call `xiaoduiyou_mini_app_contract_get`. Treat
   its live schema, vocabulary, and limits as authoritative.
3. Copy `references/mini-app-v2-example.json` as the starting point. Remove
   unused UI and data, but keep all eight required top-level keys.
4. Choose state scopes deliberately. Use `session` or `device` for UI controls,
   `member` for private member data, and `family` only for truly shared data.
5. Declare only capabilities the definition actually uses.
6. Write the raw V2 definition to a JSON file such as
   `/tmp/xdy-mini-app-weekend-board.json`. If the optional validator exists,
   run it directly against that raw definition:

   ```bash
   python "${HERMES_HOME:-$HOME/.hermes}/skills/xiaoduiyou/xiaoduiyou-doc-content-package/scripts/validate_content_package.py" \
     /tmp/xdy-mini-app-weekend-board.json
   ```

7. Inspect the document tool schema. When it exposes `mini_app_path`, pass the
   JSON file through that field and keep the tool call small; omit an inline
   `fields.ui_payloads.mini_app` copy. Otherwise, send the validated definition
   inline under `fields.ui_payloads.mini_app`.
8. Call `xiaoduiyou_documents_create` or `xiaoduiyou_documents_update`.
9. If the platform returns `INVALID_MINI_APP_DEFINITION`, correct the exact
   returned `path`, rerun the validator, and call the same document tool again
   with the same `mini_app_path`. Do not remove the mini app, switch to V1, or
   claim that the capability is unavailable.
10. Finish only after the latest document tool result contains `ok: true`,
    `applied: true`, `persisted: true`, and a non-empty `document_id`. A local
    file or clean validator result proves only local validity, not persistence.

## Choose the mode

- Use `interactive_html` for a visually free, self-contained HTML/CSS/JS page
  whose state may reset. It has no parent bridge, platform storage, or network.
- Use `mini_app` for platform-rendered search, filters, forms, collections,
  statistics, navigation, validation, member state, family state, or platform
  resources.
- Do not combine the two modes or place HTML/JavaScript inside `mini_app`.

## Document payload

Select `mini_app` and put the definition under
`fields.ui_payloads.mini_app`:

```json
{
  "title": "周末清单",
  "ui_templates": ["mini_app"],
  "fields": {
    "ui_templates": ["mini_app"],
    "ui_payloads": {
      "mini_app": {
        "schema": "xdy.mini_app.v2",
        "manifest": {
          "title": "周末清单",
          "entry_page": "home",
          "min_runtime": "2.0",
          "capabilities": ["state.family"]
        },
        "data": {
          "places": [
            {"id": "park", "name": "人民公园"},
            {"id": "museum", "name": "自然博物馆"}
          ]
        },
        "state": {
          "visited": {
            "type": "string_set",
            "scope": "family",
            "default": []
          }
        },
        "computed": {},
        "actions": {},
        "resources": {},
        "pages": {
          "home": {
            "root": {
              "type": "repeater",
              "source": {"$path": "data.places"},
              "item": {
                "type": "checkbox",
                "state_path": "visited",
                "value": {"$path": "item.id"},
                "label": {"$path": "item.name"}
              }
            }
          }
        }
      }
    }
  }
}
```

The document tool already accepts top-level `ui_templates` and merges them into
`fields.ui_templates`. Keep the payload internally consistent if both are
present.

Hermes document tools may also expose `mini_app_path`. It points to a local,
UTF-8 `.json` file whose root is the raw `xdy.mini_app.v2` definition shown
above. The connector reads and validates that file, injects it into
`fields.ui_payloads.mini_app`, and selects the `mini_app` template. Prefer this
transport for non-trivial definitions because the deferred `tool_call` bridge
otherwise has to JSON-encode the whole definition a second time.

## V2 payload and vocabulary

Every definition must contain exactly this V2 shape:

| Key | Required | Purpose |
| --- | --- | --- |
| `schema` | yes | Fixed string `xdy.mini_app.v2` |
| `manifest` | yes | Title, entry page, runtime, capabilities, theme |
| `data` | yes | Author-owned read-only JSON |
| `state` | yes | Platform-managed mutable state declarations |
| `computed` | yes | Pure derived expressions |
| `actions` | yes | Named declarative actions |
| `resources` | yes | Named read-only platform resources |
| `pages` | yes | Named pages and component trees |

Keep empty objects as `{}`. Never use removed V1 keys:

- `label`
- `content`
- `state_schema`
- `view`

Names for state, computed values, actions, resources, pages, and component IDs
must start with a letter, contain only letters/numbers/underscores, and be at
most 64 characters.

## Manifest and capabilities

```json
{
  "title": "家庭探索地图",
  "description": "一起记录去过的地方",
  "entry_page": "home",
  "min_runtime": "2.0",
  "capabilities": [
    "state.member",
    "state.family",
    "navigation",
    "share",
    "resource.child_profile.read",
    "resource.growth_diary.read"
  ],
  "theme": {
    "accent": "emerald",
    "density": "comfortable"
  }
}
```

Declare a capability only when its feature is used:

| Capability | Required when |
| --- | --- |
| `state.member` | Any state uses scope `member` |
| `state.family` | Any state uses scope `family` |
| `navigation` | More than one page, or an action uses `navigate`/`back` |
| `share` | An action uses `share` |
| `resource.child_profile.read` | A resource uses `child_profile` |
| `resource.growth_diary.read` | A resource uses `growth_diary` |

Theme values:

- `accent`: `blue`, `emerald`, `amber`, `rose`, `violet`
- `density`: `comfortable`, `compact`

## Data, state, and scopes

Treat `data` as immutable JSON published with the definition. Put user changes
in declared state.

State types:

- `string`
- `number`
- `boolean`
- `string_set`: unique string array
- `string_list`: ordered string array
- `object`: JSON object
- `list`: JSON array

Every state field must declare `type`, `scope`, and `default`.

Scopes:

| Scope | Storage and use |
| --- | --- |
| `session` | Current open runtime only; use for query text, selected item, modal state |
| `device` | Browser local storage; use for view preferences, filters, sort |
| `member` | Private to the signed-in family member |
| `family` | Shared by signed-in members of the same family |

Do not put private notes in `family`. Do not put shared checklists in `member`.

Optional validation:

- All: `required`
- Number: `min`, `max`
- String or list: `min_length`, `max_length`
- String: `pattern`; also set `max_length` no greater than 256

Example:

```json
{
  "note": {
    "type": "string",
    "scope": "member",
    "default": "",
    "required": true,
    "min_length": 2,
    "max_length": 120
  },
  "visited": {
    "type": "string_set",
    "scope": "family",
    "default": []
  }
}
```

The platform stores `member` and `family` separately and resolves revision
conflicts. Never write custom migration or synchronization code.

## Expressions and computed values

Use JSON expressions. Do not use template strings or JavaScript.

Read a path:

```json
{"$path": "data.places"}
{"$path": "state.visited"}
{"$path": "computed.visible_places"}
{"$path": "resources.child.name"}
{"$path": "context.current_page"}
{"$path": "params.from"}
{"$path": "item.name"}
{"$path": "index"}
```

Use `{"$literal": ...}` when an object must be treated as a literal value.

Allowed roots:

- `data`
- `state`
- `computed`
- `resources`
- `context`
- `params`
- repeated-item locals `item`, `index`
- action event value `event`

Allowed operators:

- Comparison: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`
- Logic: `and`, `or`, `not`, `if`
- Math: `add`, `subtract`, `multiply`, `divide`
- String/general: `concat`, `coalesce`, `lower`, `upper`, `trim`, `length`,
  `is_empty`, `contains`, `contains_ci`, `starts_with`, `ends_with`, `includes`
- Collections: `filter`, `map`, `sort`, `search`, `count`, `sum`, `first`, `group`

Example:

```json
{
  "$op": "filter",
  "input": {"$path": "data.places"},
  "where": {
    "$op": "includes",
    "args": [
      {"$path": "state.visited"},
      {"$path": "item.id"}
    ]
  }
}
```

Put reusable derived expressions in `computed`. Computed references must exist
and must not form cycles.

## Actions

Components reference actions by name. Never place an action object directly on
a button and never use an undeclared name.

State actions:

- `state.set`
- `state.toggle`
- `state.increment`
- `state.add`
- `state.remove`
- `state.move`
- `state.clear`
- `state.batch`

Mutation types are not interchangeable:

- `state.toggle` is only for a `boolean` field.
- `state.increment` is only for a `number` field.
- `state.add` and `state.remove` are for `string_set`, `string_list`, or
  `list`.
- `state.move` is only for `string_list` or `list`.
- A `checkbox` bound to a `string_set` already adds/removes its `value`; it
  does not need a separate `state.toggle` action.

If a button must toggle membership in a shared set, declare add/remove actions
and select between them with `conditional`:

```json
{
  "actions": {
    "mark_complete": {
      "type": "state.add",
      "path": "completed",
      "value": {"$path": "item.id"}
    },
    "unmark_complete": {
      "type": "state.remove",
      "path": "completed",
      "value": {"$path": "item.id"}
    },
    "toggle_complete": {
      "type": "conditional",
      "condition": {
        "$op": "includes",
        "args": [
          {"$path": "state.completed"},
          {"$path": "item.id"}
        ]
      },
      "then": "unmark_complete",
      "else": "mark_complete"
    }
  }
}
```

Flow and platform actions:

- `sequence`
- `conditional`
- `navigate`
- `back`
- `toast`
- `resource.refresh`
- `share`

Example:

```json
{
  "actions": {
    "open_details": {
      "type": "state.batch",
      "changes": [
        {
          "type": "state.set",
          "path": "selected_id",
          "value": {"$path": "item.id"}
        },
        {
          "type": "state.set",
          "path": "details_open",
          "value": true
        }
      ]
    },
    "close_details": {
      "type": "state.set",
      "path": "details_open",
      "value": false
    },
    "go_stats": {
      "type": "navigate",
      "page": "stats"
    }
  }
}
```

Button reference:

```json
{
  "type": "button",
  "label": "查看详情",
  "action": "open_details"
}
```

Action references must not form cycles.

## Pages and components

Declare at least one page. `manifest.entry_page` must name a declared page.

```json
{
  "home": {
    "title": "首页",
    "root": {
      "type": "text",
      "value": "你好"
    }
  }
}
```

All components may use `visible` and `enabled` expressions. Component `id` is
optional but must be unique across the mini app.

Component vocabulary:

| Category | Types |
| --- | --- |
| Layout | `column`, `row`, `grid`, `card`, `section` |
| Spacing | `divider`, `spacer` |
| Text/media | `text`, `image`, `icon`, `tag` |
| Status | `progress`, `stat`, `alert`, `empty` |
| Input | `checkbox`, `switch`, `text_input`, `textarea`, `number_input`, `date_input`, `select`, `radio`, `slider` |
| Interaction | `button`, `tabs`, `form`, `modal` |
| Data | `repeater`, `collection`, `table`, `bar_chart` |

Important bindings:

- `checkbox`: boolean state, or `string_set` plus a `value`
- `switch`: boolean state
- `text_input`, `textarea`, `date_input`: string state
- `number_input`, `slider`: number state
- `select`, `radio`: string/number state plus `{value,label}` options
- `tabs`: string state plus tab entries
- `form`: declared `fields`, `children`, and a declared `submit_action`
- `modal`: boolean `state_path`
- `repeater`/`collection`: `source` expression and an `item` component tree
- `table`: `source` plus 1-20 columns
- `bar_chart`: `source`, `label`, and numeric `value` expressions

Text variants: `title`, `subtitle`, `body`, `caption`.

Button variants: default, `secondary`, `danger`.

Alert/toast tones: `info`, `success`, `warning`, `error`.

## Collection browser

Use `collection.browser` instead of rebuilding common list controls:

```json
{
  "type": "collection",
  "source": {"$path": "data.places"},
  "browser": {
    "page_size": 30,
    "search": {
      "state_path": "query",
      "placeholder": "搜索地点",
      "item_paths": ["name", "city", "tags"]
    },
    "filters": [
      {
        "label": "城市",
        "state_path": "cities",
        "item_path": "city",
        "multiple": true,
        "options": "auto"
      }
    ],
    "sort": {
      "state_path": "sort",
      "label": "排序",
      "options": [
        {
          "value": "score",
          "label": "评分优先",
          "by": [
            {"item_path": "score", "direction": "desc"},
            {"item_path": "name", "direction": "asc"}
          ]
        }
      ]
    }
  },
  "item": {
    "type": "text",
    "value": {"$path": "item.name"}
  }
}
```

Rules:

- Search state: `string`
- Single filter state: `string` or `number`
- Multiple filter state: `string_set`
- Filter operators: `eq`, `contains`, `gte`, `lte`
- Options: explicit `{value,label}` array or `"auto"`
- Sort state: `string`; each option has at most five sort keys
- `page_size`: 1-200; default 30
- One collection processes at most 5000 items

## Platform resources

Declare read-only resources:

```json
{
  "child": {"type": "child_profile"},
  "diary": {"type": "growth_diary"}
}
```

Resource types:

- `child_profile`
- `growth_diary`

Declare the matching capability. Public anonymous views receive no private
family resource data. Mini-app actions cannot write platform resources.

## Updates, sharing, and limits

The author updates the definition, not user state. The platform keeps a value
only when its field name, type, scope, and validation remain compatible.
Removed or incompatible fields reset or are deleted deterministically.

Another family collecting a public mini app receives an independent document
collection and independent `member`/`family` state while reading the author's
latest definition. Anonymous viewing creates no account, session, or document.

Hard limits:

- JSON payload: 1 MiB
- State fields: 200
- Computed values: 100
- Actions: 100
- Resources: 20
- Pages: 20
- View nodes: 1000
- Expression/component nesting depth: 30
- Children per parent: 200
- Collection items processed: 5000

The runtime never executes author JavaScript, HTML, CSS, dynamic imports, or
arbitrary network requests. Paths may not access `__proto__`, `prototype`, or
`constructor`.

## Validation failures

The backend is authoritative. A failed create/update returns structured data:

- `error: INVALID_MINI_APP_DEFINITION`
- `capability_available: true`
- `expected_schema: xdy.mini_app.v2`
- exact `path`
- actionable `reason`
- optional `expected`
- `contract_endpoint`
- `skill_reference`

Correct the field at `path`, reread the referenced section or call
`xiaoduiyou_mini_app_contract_get`, rerun the local validator, then retry the
same create/update with the same `mini_app_path`. Do not send a completion reply
until that later tool call returns `ok: true`, `applied: true`,
`persisted: true`, and a non-empty `document_id`.

Do not:

- retry with V1
- remove `mini_app` without the user's instruction
- silently replace it with `interactive_html`
- claim mini-app support is unavailable
- invent unsupported components, actions, expression operators, or resources

Use `references/mini-app-v2-example.json` as the complete executable reference.
