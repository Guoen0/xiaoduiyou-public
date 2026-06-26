#!/usr/bin/env python3
"""Verify the Codex installer packages the Xiaoduiyou runtime skill contract."""

from __future__ import annotations

import filecmp
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PLUGIN = ROOT / "plugins" / "xiaoduiyou-runtime-skills"
RUNTIME_SKILLS = [
    "xiaoduiyou-im",
    "xiaoduiyou-doc-content-package",
    "xiaoduiyou-growth-diary",
    "xiaoduiyou-child-profile",
    "xiaoduiyou-feedback-issues",
]
RUNTIME_API_REFERENCE_SKILLS = [
    "xiaoduiyou-im",
    "xiaoduiyou-doc-content-package",
    "xiaoduiyou-growth-diary",
]


def fail(message: str) -> None:
    print(f"codex install contract verification failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_text(path: Path, needles: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            fail(f"{path.relative_to(ROOT)} missing {needle!r}")


def compare_dirs(source: Path, packaged: Path) -> None:
    comparison = filecmp.dircmp(source, packaged, ignore=["__pycache__"])
    if comparison.left_only or comparison.right_only or comparison.diff_files:
        fail(
            "runtime skill package drift for "
            f"{source.relative_to(ROOT)}: "
            f"left_only={comparison.left_only}, "
            f"right_only={comparison.right_only}, "
            f"diff_files={comparison.diff_files}"
        )
    for name in comparison.common_dirs:
        compare_dirs(source / name, packaged / name)


def main() -> None:
    manifest_path = RUNTIME_PLUGIN / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != "xiaoduiyou-runtime-skills":
        fail("runtime skills plugin manifest name mismatch")
    if manifest.get("skills") != "./skills/":
        fail("runtime skills plugin manifest must expose ./skills/")

    for skill in RUNTIME_SKILLS:
        source = ROOT / "skills" / skill
        packaged = RUNTIME_PLUGIN / "skills" / skill
        if not (packaged / "SKILL.md").is_file():
            fail(f"packaged skill missing {skill}/SKILL.md")
        compare_dirs(source, packaged)

    require_text(
        ROOT / "scripts" / "install-codex-runner.sh",
        [
            "xiaoduiyou-runtime-skills",
            "codex plugin add xiaoduiyou-runtime-skills@personal",
            "xiaoduiyou-im",
            "xiaoduiyou-doc-content-package",
            "xiaoduiyou-growth-diary",
            "xiaoduiyou-child-profile",
            "xiaoduiyou-feedback-issues",
        ],
    )
    require_text(
        ROOT / "plugins" / "xiaoduiyou-codex-platform" / "scripts" / "xiaoduiyou_mcp.py",
        [
            "CONNECTOR_VERSION = \"2026.6.26-codex.1\"",
            "\"name\": \"xiaoduiyou_im_send\"",
            "\"name\": \"xiaoduiyou_interactive_request_create\"",
            "\"name\": \"xiaoduiyou_interactive_request_wait\"",
            "\"name\": \"xiaoduiyou_child_get\"",
            "\"name\": \"xiaoduiyou_child_patch\"",
            "\"/api/agent/im/send\"",
            "\"/api/agent/interactive-requests\"",
            "tool-progress",
            "input_text",
            "input_image",
        ],
    )
    require_text(
        ROOT / "scripts" / "install-openclaw.sh",
        [
            "xiaoduiyou_im_send",
            "openclaw plugins install",
            "OPENCLAW_HOME_ROOT",
            ".openclaw/.openclaw/workspace/skills",
            "could not update agents.list",
        ],
    )
    require_text(
        ROOT / "README.md",
        [
            "xiaoduiyou-runtime-skills",
            "xiaoduiyou-im",
            "xiaoduiyou-doc-content-package",
            "xiaoduiyou-growth-diary",
            "xiaoduiyou-child-profile",
            "xiaoduiyou-feedback-issues",
            "xiaoduiyou_im_send",
            "xiaoduiyou_interactive_request_create",
            "xiaoduiyou_interactive_request_wait",
            "channel directory",
            "xiaoduiyou:主对话",
        ],
    )
    require_text(
        ROOT / "plugins" / "xiaoduiyou-hermes-platform" / "xiaoduiyou_hermes_platform" / "adapter.py",
        [
            "async def list_channels",
            "\"id\": \"default\"",
            "\"name\": \"主对话\"",
            "\"home_channel\"",
            "_write_xiaoduiyou_channel_directory",
        ],
    )
    for skill in RUNTIME_API_REFERENCE_SKILLS:
        require_text(
            ROOT / "skills" / skill / "references" / "runtime-api-reference.md",
            [
                "POST /api/agent/im/send",
                "xiaoduiyou_im_send",
                "default",
                "主对话",
                "Do not use it for cron/background/Home delivery.",
            ],
        )

    print("Codex install contract verification passed")


if __name__ == "__main__":
    main()
