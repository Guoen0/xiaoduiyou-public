#!/usr/bin/env python3
"""Validate Xiaoduiyou content-package JSON before creating/updating documents.

Accepts either:
- a full document tool payload with `fields.publish_notes` / `ui_templates`, or
- an artifact-like object with `blocks.ui_templates` / `blocks.publish_notes`, or
- a raw fields object with `ui_templates` / `publish_notes`.

This is a lightweight guardrail, not a full backend schema validator.
"""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path
from typing import Any

URL_RE = re.compile(r"^https?://", re.I)
UI_PAYLOAD_TEMPLATES = {"interactive_html", "mini_app"}
MINI_APP_SCHEMA = "xdy.mini_app.v2"
MINI_APP_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
MINI_APP_CAPABILITIES = {
    "state.member",
    "state.family",
    "navigation",
    "share",
    "resource.child_profile.read",
    "resource.growth_diary.read",
}
MINI_APP_STATE_TYPES = {"string", "number", "boolean", "string_set", "string_list", "object", "list"}
MINI_APP_STATE_SCOPES = {"session", "device", "member", "family"}
MINI_APP_ACTION_TYPES = {
    "state.set",
    "state.toggle",
    "state.increment",
    "state.add",
    "state.remove",
    "state.move",
    "state.clear",
    "state.batch",
    "sequence",
    "conditional",
    "navigate",
    "back",
    "toast",
    "resource.refresh",
    "share",
}
MINI_APP_COMPONENT_TYPES = {
    "column",
    "row",
    "grid",
    "card",
    "section",
    "divider",
    "spacer",
    "text",
    "image",
    "icon",
    "tag",
    "progress",
    "stat",
    "alert",
    "empty",
    "checkbox",
    "switch",
    "text_input",
    "textarea",
    "number_input",
    "date_input",
    "select",
    "radio",
    "slider",
    "button",
    "repeater",
    "collection",
    "table",
    "bar_chart",
    "tabs",
    "form",
    "modal",
}
MINI_APP_RESOURCE_CAPABILITY = {
    "child_profile": "resource.child_profile.read",
    "growth_diary": "resource.growth_diary.read",
}
MINI_APP_LEGACY_KEYS = {"label", "content", "state_schema", "view"}


def _mini_app_default_matches(state_type: str, value: Any) -> bool:
    if state_type == "string":
        return isinstance(value, str)
    if state_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if state_type == "boolean":
        return isinstance(value, bool)
    if state_type in {"string_set", "string_list"}:
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if state_type == "object":
        return isinstance(value, dict)
    if state_type == "list":
        return isinstance(value, list)
    return False


def _mini_app_named_object(value: Any, path: str, maximum: int, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return {}
    if len(value) > maximum:
        errors.append(f"{path} must contain at most {maximum} entries")
    for name in value:
        if not MINI_APP_IDENTIFIER_RE.fullmatch(str(name)):
            errors.append(f"{path}.{name} must be a valid identifier")
    return value


def _validate_mini_app_action(
    action: Any,
    path: str,
    state: dict[str, Any],
    actions: dict[str, Any],
    pages: dict[str, Any],
    resources: dict[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(action, dict):
        errors.append(f"{path} must be an action object")
        return
    action_type = action.get("type")
    if action_type not in MINI_APP_ACTION_TYPES:
        errors.append(f"{path}.type must be a supported V2 action")
        return

    def state_path(change: dict[str, Any], change_path: str) -> None:
        field_name = change.get("path")
        if not isinstance(field_name, str) or field_name not in state:
            errors.append(f"{change_path}.path must name a declared state field")

    if isinstance(action_type, str) and action_type.startswith("state.") and action_type != "state.batch":
        state_path(action, path)
    elif action_type == "state.batch":
        changes = action.get("changes")
        if not isinstance(changes, list) or not changes:
            errors.append(f"{path}.changes must be a non-empty array")
        else:
            for index, change in enumerate(changes):
                change_path = f"{path}.changes[{index}]"
                if not isinstance(change, dict) or change.get("type") not in {
                    "state.set",
                    "state.toggle",
                    "state.increment",
                    "state.add",
                    "state.remove",
                    "state.move",
                    "state.clear",
                }:
                    errors.append(f"{change_path} must be a supported state mutation")
                else:
                    state_path(change, change_path)
    elif action_type == "sequence":
        refs = action.get("actions")
        if not isinstance(refs, list) or not refs or any(ref not in actions for ref in refs):
            errors.append(f"{path}.actions must name declared actions")
    elif action_type == "conditional":
        for branch in ("then", "else"):
            ref = action.get(branch)
            if ref is not None and ref not in actions:
                errors.append(f"{path}.{branch} must name a declared action")
    elif action_type == "navigate" and action.get("page") not in pages:
        errors.append(f"{path}.page must name a declared page")
    elif action_type == "resource.refresh":
        resource = action.get("resource")
        if resource is not None and resource not in resources:
            errors.append(f"{path}.resource must name a declared resource")


def _validate_mini_app_node(
    node: Any,
    path: str,
    state: dict[str, Any],
    actions: dict[str, Any],
    errors: list[str],
    node_ids: set[str],
    node_count: list[int],
    depth: int = 0,
) -> None:
    if not isinstance(node, dict):
        errors.append(f"{path} must be a component object")
        return
    if depth > 30:
        errors.append(f"{path} exceeds the maximum nesting depth of 30")
        return
    node_count[0] += 1
    if node_count[0] > 1000:
        errors.append("mini_app pages contain more than 1000 component nodes")
        return
    node_type = node.get("type")
    if node_type not in MINI_APP_COMPONENT_TYPES:
        errors.append(f"{path}.type must be a supported V2 component")
        return
    node_id = node.get("id")
    if node_id is not None:
        if not isinstance(node_id, str) or not MINI_APP_IDENTIFIER_RE.fullmatch(node_id):
            errors.append(f"{path}.id must be a valid identifier")
        elif node_id in node_ids:
            errors.append(f"{path}.id must be unique")
        else:
            node_ids.add(node_id)

    def require_state(allowed_types: set[str] | None = None) -> None:
        state_path = node.get("state_path")
        if not isinstance(state_path, str) or state_path not in state:
            errors.append(f"{path}.state_path must name a declared state field")
            return
        if allowed_types and state[state_path].get("type") not in allowed_types:
            errors.append(f"{path}.state_path has an incompatible state type")

    if node_type in {"column", "row", "grid", "card", "section"}:
        children = node.get("children")
        if not isinstance(children, list) or len(children) > 200:
            errors.append(f"{path}.children must be an array with at most 200 nodes")
        else:
            for index, child in enumerate(children):
                _validate_mini_app_node(child, f"{path}.children[{index}]", state, actions, errors, node_ids, node_count, depth + 1)
    elif node_type == "checkbox":
        require_state({"boolean", "string_set"})
        state_path = node.get("state_path")
        if isinstance(state_path, str) and state_path in state and state[state_path].get("type") == "string_set" and "value" not in node:
            errors.append(f"{path}.value is required for string_set checkbox state")
    elif node_type == "switch":
        require_state({"boolean"})
    elif node_type in {"text_input", "textarea", "date_input"}:
        require_state({"string"})
    elif node_type in {"number_input", "slider"}:
        require_state({"number"})
    elif node_type in {"select", "radio"}:
        require_state({"string", "number"})
        if not isinstance(node.get("options"), list):
            errors.append(f"{path}.options must be an array")
    elif node_type == "button":
        if node.get("action") not in actions:
            errors.append(f"{path}.action must name a declared action")
        if "label" not in node:
            errors.append(f"{path}.label is required")
    elif node_type in {"repeater", "collection"}:
        if "source" not in node:
            errors.append(f"{path}.source is required")
        _validate_mini_app_node(node.get("item"), f"{path}.item", state, actions, errors, node_ids, node_count, depth + 1)
        browser = node.get("browser")
        if node_type == "collection" and browser is not None:
            if not isinstance(browser, dict):
                errors.append(f"{path}.browser must be an object")
            elif "page_size" in browser and (
                not isinstance(browser["page_size"], int) or not 1 <= browser["page_size"] <= 200
            ):
                errors.append(f"{path}.browser.page_size must be an integer from 1 to 200")
    elif node_type == "table":
        columns = node.get("columns")
        if "source" not in node or not isinstance(columns, list) or not 1 <= len(columns) <= 20:
            errors.append(f"{path} requires source and 1-20 columns")
    elif node_type == "bar_chart":
        for field in ("source", "label", "value"):
            if field not in node:
                errors.append(f"{path}.{field} is required")
    elif node_type == "tabs":
        require_state({"string"})
        tabs = node.get("tabs")
        if not isinstance(tabs, list) or not 1 <= len(tabs) <= 12:
            errors.append(f"{path}.tabs must contain 1-12 entries")
        else:
            for index, tab in enumerate(tabs):
                if not isinstance(tab, dict) or not isinstance(tab.get("value"), str) or not isinstance(tab.get("label"), str):
                    errors.append(f"{path}.tabs[{index}] requires string value and label")
                    continue
                _validate_mini_app_node(tab.get("content"), f"{path}.tabs[{index}].content", state, actions, errors, node_ids, node_count, depth + 1)
    elif node_type == "form":
        fields = node.get("fields")
        if not isinstance(fields, list) or any(field not in state for field in fields):
            errors.append(f"{path}.fields must name declared state fields")
        if node.get("submit_action") not in actions:
            errors.append(f"{path}.submit_action must name a declared action")
        children = node.get("children")
        if not isinstance(children, list):
            errors.append(f"{path}.children must be an array")
        else:
            for index, child in enumerate(children):
                _validate_mini_app_node(child, f"{path}.children[{index}]", state, actions, errors, node_ids, node_count, depth + 1)
    elif node_type == "modal":
        require_state({"boolean"})
        children = node.get("children")
        if not isinstance(children, list):
            errors.append(f"{path}.children must be an array")
        else:
            for index, child in enumerate(children):
                _validate_mini_app_node(child, f"{path}.children[{index}]", state, actions, errors, node_ids, node_count, depth + 1)


def validate_mini_app_v2(mini_app: Any) -> list[str]:
    errors: list[str] = []
    prefix = "ui_payloads.mini_app"
    if not isinstance(mini_app, dict):
        return [f"{prefix} must be an object"]
    try:
        if len(json.dumps(mini_app, ensure_ascii=False).encode("utf-8")) > 1024 * 1024:
            errors.append(f"{prefix} must be at most 1 MiB")
    except (TypeError, ValueError):
        errors.append(f"{prefix} must contain JSON-safe values")
        return errors
    if mini_app.get("schema") != MINI_APP_SCHEMA:
        errors.append(f"{prefix}.schema must be {MINI_APP_SCHEMA}; V1 is not supported")
    for legacy_key in sorted(MINI_APP_LEGACY_KEYS & mini_app.keys()):
        errors.append(f"{prefix}.{legacy_key} is a removed V1 key")
    for key in ("manifest", "data", "state", "computed", "actions", "resources", "pages"):
        if not isinstance(mini_app.get(key), dict):
            errors.append(f"{prefix}.{key} must be an object")

    manifest = mini_app.get("manifest") if isinstance(mini_app.get("manifest"), dict) else {}
    data = mini_app.get("data") if isinstance(mini_app.get("data"), dict) else {}
    del data
    state = _mini_app_named_object(mini_app.get("state"), f"{prefix}.state", 200, errors)
    computed = _mini_app_named_object(mini_app.get("computed"), f"{prefix}.computed", 100, errors)
    del computed
    actions = _mini_app_named_object(mini_app.get("actions"), f"{prefix}.actions", 100, errors)
    resources = _mini_app_named_object(mini_app.get("resources"), f"{prefix}.resources", 20, errors)
    pages = _mini_app_named_object(mini_app.get("pages"), f"{prefix}.pages", 20, errors)

    if not isinstance(manifest.get("title"), str) or not manifest["title"].strip():
        errors.append(f"{prefix}.manifest.title must be a non-empty string")
    if manifest.get("min_runtime") != "2.0":
        errors.append(f"{prefix}.manifest.min_runtime must be 2.0")
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, list) or any(capability not in MINI_APP_CAPABILITIES for capability in capabilities):
        errors.append(f"{prefix}.manifest.capabilities must contain only supported capabilities")
        capabilities_set: set[str] = set()
    else:
        capabilities_set = set(capabilities)
    entry_page = manifest.get("entry_page")
    if not isinstance(entry_page, str) or entry_page not in pages:
        errors.append(f"{prefix}.manifest.entry_page must name a declared page")

    used_capabilities: set[str] = set()
    for name, field in state.items():
        path = f"{prefix}.state.{name}"
        if not isinstance(field, dict):
            errors.append(f"{path} must be an object")
            continue
        state_type = field.get("type")
        scope = field.get("scope")
        if state_type not in MINI_APP_STATE_TYPES:
            errors.append(f"{path}.type must be a supported state type")
        if scope not in MINI_APP_STATE_SCOPES:
            errors.append(f"{path}.scope must be session, device, member, or family")
        if "default" not in field:
            errors.append(f"{path}.default is required")
        elif isinstance(state_type, str) and not _mini_app_default_matches(state_type, field.get("default")):
            errors.append(f"{path}.default must match type {state_type}")
        if scope == "member":
            used_capabilities.add("state.member")
        if scope == "family":
            used_capabilities.add("state.family")

    for name, resource in resources.items():
        path = f"{prefix}.resources.{name}"
        if not isinstance(resource, dict) or resource.get("type") not in MINI_APP_RESOURCE_CAPABILITY:
            errors.append(f"{path}.type must be child_profile or growth_diary")
            continue
        used_capabilities.add(MINI_APP_RESOURCE_CAPABILITY[resource["type"]])

    if len(pages) > 1:
        used_capabilities.add("navigation")
    for name, action in actions.items():
        _validate_mini_app_action(action, f"{prefix}.actions.{name}", state, actions, pages, resources, errors)
        if isinstance(action, dict):
            if action.get("type") in {"navigate", "back"}:
                used_capabilities.add("navigation")
            if action.get("type") == "share":
                used_capabilities.add("share")

    missing_capabilities = sorted(used_capabilities - capabilities_set)
    if missing_capabilities:
        errors.append(f"{prefix}.manifest.capabilities is missing: {', '.join(missing_capabilities)}")

    node_ids: set[str] = set()
    node_count = [0]
    for name, page in pages.items():
        path = f"{prefix}.pages.{name}"
        if not isinstance(page, dict):
            errors.append(f"{path} must be an object")
            continue
        _validate_mini_app_node(page.get("root"), f"{path}.root", state, actions, errors, node_ids, node_count)
    if not pages:
        errors.append(f"{prefix}.pages must contain at least one page")
    return errors


def load_payload(path_or_json: str) -> Any:
    p = Path(path_or_json)
    raw = p.read_text(encoding="utf-8") if p.exists() else path_or_json
    return json.loads(raw)


def dig_payload(obj: dict[str, Any]) -> dict[str, Any]:
    if isinstance(obj.get("fields"), dict):
        return obj["fields"]
    if isinstance(obj.get("blocks"), dict):
        return obj["blocks"]
    if isinstance(obj.get("artifact"), dict) and isinstance(obj["artifact"].get("blocks"), dict):
        return obj["artifact"]["blocks"]
    return obj


def validate(obj: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(obj, dict):
        return ["Top-level payload must be a JSON object"], []
    data = dig_payload(obj)
    templates = data.get("ui_templates")
    publish_notes = data.get("publish_notes")
    ui_payloads = data.get("ui_payloads")
    if templates is None and publish_notes is None and ui_payloads is None:
        warnings.append("No ui_templates, publish_notes, or ui_payloads found; this may be a process-only document, not a content package.")
    if templates is not None:
        if not isinstance(templates, list) or not all(isinstance(x, str) for x in templates):
            errors.append("ui_templates must be a list of strings")
    if publish_notes is not None and not isinstance(publish_notes, dict):
        errors.append("publish_notes must be an object keyed by template/platform")
    if ui_payloads is not None and not isinstance(ui_payloads, dict):
        errors.append("ui_payloads must be an object keyed by template")
    if isinstance(templates, list):
        for t in templates:
            payloads = ui_payloads if isinstance(ui_payloads, dict) else {}
            notes = publish_notes if isinstance(publish_notes, dict) else {}
            result_data = payloads if t in UI_PAYLOAD_TEMPLATES else notes
            result_field = "ui_payloads" if t in UI_PAYLOAD_TEMPLATES else "publish_notes"
            if t not in result_data:
                warnings.append(f"ui_templates includes {t!r} but {result_field} has no matching key")
    if isinstance(publish_notes, dict):
        for key, note in publish_notes.items():
            if isinstance(templates, list) and key not in templates:
                warnings.append(f"publish_notes has {key!r} but ui_templates does not include it")
            if not isinstance(note, dict):
                errors.append(f"publish_notes.{key} must be an object")
                continue
            for field in ("title", "body"):
                if field in note and not isinstance(note[field], str):
                    errors.append(f"publish_notes.{key}.{field} must be a string")
            imgs = note.get("images")
            if imgs is not None:
                if not isinstance(imgs, list):
                    errors.append(f"publish_notes.{key}.images must be a list")
                else:
                    for i, url in enumerate(imgs):
                        if not isinstance(url, str) or not URL_RE.match(url):
                            errors.append(f"publish_notes.{key}.images[{i}] must be an http(s) URL, not a local path")
            body = str(note.get("body") or "")
            if any(marker in body.lower() for marker in ["source_markdown", "过程材料", "证据", "raw:", "debug"]):
                warnings.append(f"publish_notes.{key}.body may contain process/debug material; keep visible publish tabs final-only")
    if isinstance(ui_payloads, dict):
        interactive_html = ui_payloads.get("interactive_html")
        if interactive_html is not None:
            if not isinstance(interactive_html, dict):
                errors.append("ui_payloads.interactive_html must be an object")
            elif interactive_html.get("schema") != "xdy.interactive_html.v1":
                errors.append("ui_payloads.interactive_html.schema must be xdy.interactive_html.v1")
            elif not isinstance(interactive_html.get("html"), str) or not interactive_html["html"].strip():
                errors.append("ui_payloads.interactive_html.html must be a non-empty string")
        mini_app = ui_payloads.get("mini_app")
        if mini_app is not None:
            errors.extend(validate_mini_app_v2(mini_app))
    if isinstance(ui_payloads, dict) and isinstance(templates, list):
        for key in ui_payloads:
            if key in UI_PAYLOAD_TEMPLATES and key not in templates:
                warnings.append(f"ui_payloads has {key!r} but ui_templates does not include it")
    source_md = data.get("source_markdown")
    if source_md is not None and not isinstance(source_md, str):
        errors.append("source_markdown must be a string")
    return errors, warnings


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("payload", help="Path to JSON file or raw JSON string")
    args = p.parse_args()
    try:
        obj = load_payload(args.payload)
        errors, warnings = validate(obj)
    except Exception as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 2
    ok = not errors
    print(json.dumps({"ok": ok, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
