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
    if templates is None and publish_notes is None:
        warnings.append("No ui_templates or publish_notes found; this may be a process-only document, not a content package.")
    if templates is not None:
        if not isinstance(templates, list) or not all(isinstance(x, str) for x in templates):
            errors.append("ui_templates must be a list of strings")
    if publish_notes is not None and not isinstance(publish_notes, dict):
        errors.append("publish_notes must be an object keyed by template/platform")
    if isinstance(templates, list) and isinstance(publish_notes, dict):
        for t in templates:
            if t not in publish_notes:
                warnings.append(f"ui_templates includes {t!r} but publish_notes has no matching key")
        for key, note in publish_notes.items():
            if key not in templates:
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
