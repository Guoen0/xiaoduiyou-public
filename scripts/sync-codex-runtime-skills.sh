#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLIC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="$PUBLIC_DIR/plugins/xiaoduiyou-runtime-skills/skills"

mkdir -p "$TARGET_DIR"

for skill in xiaoduiyou-im xiaoduiyou-doc-content-package xiaoduiyou-growth-diary xiaoduiyou-child-profile xiaoduiyou-feedback-issues; do
  rm -rf "$TARGET_DIR/$skill"
  rsync -a --delete \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "$PUBLIC_DIR/skills/$skill/" \
    "$TARGET_DIR/$skill/"
done

echo "Synced Codex runtime skills into plugins/xiaoduiyou-runtime-skills/skills"
