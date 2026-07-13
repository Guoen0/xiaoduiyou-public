#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLIC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-${HOME}/.hermes}"
SOURCE_DIR="${HERMES_SEARCH_SKILL_SOURCE:-${HERMES_HOME_DIR}/skills/_private/xiaoduiyou-search}"
TARGET_DIR="$PUBLIC_DIR/hermes-skills/xiaoduiyou-search"

for required in \
  SKILL.md \
  scripts/tikhub_search.py \
  scripts/web_search.py \
  references/search-routing.md \
  references/legacy-social-providers.md; do
  if [ ! -f "$SOURCE_DIR/$required" ]; then
    echo "Missing Hermes search skill file: $SOURCE_DIR/$required" >&2
    exit 2
  fi
done

mkdir -p "$TARGET_DIR"
rsync -a --delete \
  --exclude '.DS_Store' \
  --exclude '.env' \
  --exclude '.tikhub_env' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$SOURCE_DIR/" "$TARGET_DIR/"

if find "$TARGET_DIR" -type f \( -name '.env' -o -name '.tikhub_env' -o -name '*.pyc' \) -print -quit | grep -q .; then
  echo "Refusing to package Hermes search secrets or cache files." >&2
  exit 2
fi

echo "Synced Hermes search skill into hermes-skills/xiaoduiyou-search"
