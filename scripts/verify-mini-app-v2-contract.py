#!/usr/bin/env python3
"""Verify the public Agent skill, runtime mirror, and Hermes V2 contract stay aligned."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "xiaoduiyou-doc-content-package"
MIRROR = ROOT / "plugins" / "xiaoduiyou-runtime-skills" / "skills" / "xiaoduiyou-doc-content-package"
VALIDATOR = SKILL / "scripts" / "validate_content_package.py"
EXAMPLE = SKILL / "references" / "mini-app-v2-example.json"
ADAPTER = ROOT / "plugins" / "xiaoduiyou-hermes-platform" / "xiaoduiyou_hermes_platform" / "adapter.py"
PLUGIN_YAML = ROOT / "plugins" / "xiaoduiyou-hermes-platform" / "xiaoduiyou_hermes_platform" / "plugin.yaml"
RUNTIME_MANIFEST = ROOT / "plugins" / "xiaoduiyou-runtime-skills" / ".codex-plugin" / "plugin.json"


def load_validator():
    spec = importlib.util.spec_from_file_location("xiaoduiyou_content_package_validator", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load content-package validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def comparable_files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def main() -> int:
    failures: list[str] = []
    validator = load_validator()
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    valid_payload = {
        "ui_templates": ["mini_app"],
        "ui_payloads": {"mini_app": example},
    }
    valid_errors, valid_warnings = validator.validate(valid_payload)
    if valid_errors or valid_warnings:
        failures.append(f"V2 example did not validate cleanly: errors={valid_errors}, warnings={valid_warnings}")

    v1_example = dict(example)
    v1_example["schema"] = "xdy.mini_app.v1"
    v1_errors, _ = validator.validate({
        "ui_templates": ["mini_app"],
        "ui_payloads": {"mini_app": v1_example},
    })
    if not any("V1 is not supported" in error for error in v1_errors):
        failures.append("Validator did not explicitly reject xdy.mini_app.v1")

    missing_capability_example = json.loads(json.dumps(example))
    missing_capability_example["manifest"]["capabilities"].remove("state.family")
    capability_errors, _ = validator.validate({
        "ui_templates": ["mini_app"],
        "ui_payloads": {"mini_app": missing_capability_example},
    })
    if not any("state.family" in error for error in capability_errors):
        failures.append("Validator did not detect a missing state.family capability")

    missing_action_example = json.loads(json.dumps(example))
    missing_action_example["pages"]["home"]["root"]["children"][3]["children"][0]["action"] = "missing_action"
    action_errors, _ = validator.validate({
        "ui_templates": ["mini_app"],
        "ui_payloads": {"mini_app": missing_action_example},
    })
    if not any("must name a declared action" in error for error in action_errors):
        failures.append("Validator did not detect an undeclared component action")

    if comparable_files(SKILL) != comparable_files(MIRROR):
        failures.append("Top-level content-package skill and runtime-skill mirror differ")

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    plugin_yaml = PLUGIN_YAML.read_text(encoding="utf-8")
    adapter_version = re.search(r'XIAODUIYOU_HERMES_PLUGIN_VERSION = "([^"]+)"', adapter_source)
    manifest_version = re.search(r"(?m)^version:\s*(\S+)\s*$", plugin_yaml)
    if not adapter_version or not manifest_version or adapter_version.group(1) != manifest_version.group(1):
        failures.append("Hermes adapter constant and plugin.yaml version differ")
    if "xiaoduiyou_mini_app_contract_get" not in adapter_source:
        failures.append("Hermes adapter does not expose the live mini-app contract tool")
    if "schema xdy.mini_app.v1" in adapter_source:
        failures.append("Hermes adapter still instructs Agents to author V1")

    runtime_manifest = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    if runtime_manifest.get("version") != "0.1.16":
        failures.append("Runtime-skill plugin version must be 0.1.16 for the V2 skill release")

    adjacent_main_example = ROOT.parent / "xiaoduiyou" / "docs" / "examples" / "mini-app-v2-places.json"
    if adjacent_main_example.exists() and adjacent_main_example.read_bytes() != EXAMPLE.read_bytes():
        failures.append("Bundled Agent example differs from the adjacent main runtime example")

    print(json.dumps({
        "ok": not failures,
        "schema": example.get("schema"),
        "hermes_plugin_version": adapter_version.group(1) if adapter_version else None,
        "runtime_skills_version": runtime_manifest.get("version"),
        "failures": failures,
    }, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
