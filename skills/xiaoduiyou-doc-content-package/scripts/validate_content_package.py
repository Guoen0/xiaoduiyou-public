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
            if not isinstance(mini_app, dict):
                errors.append("ui_payloads.mini_app must be an object")
            else:
                if mini_app.get("schema") != "xdy.mini_app.v1":
                    errors.append("ui_payloads.mini_app.schema must be xdy.mini_app.v1")
                if not isinstance(mini_app.get("state_schema"), dict):
                    errors.append("ui_payloads.mini_app.state_schema must be an object")
                if not isinstance(mini_app.get("view"), dict):
                    errors.append("ui_payloads.mini_app.view must be an object")
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
