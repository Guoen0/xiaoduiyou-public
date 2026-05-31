#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 /absolute/path/to/xiaoduiyou-app-repo" >&2
  exit 2
fi

SRC=$1
DST=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if [ ! -d "$SRC/public/plugins/xiaoduiyou-platform" ]; then
  echo "Missing source Hermes plugin: $SRC/public/plugins/xiaoduiyou-platform" >&2
  exit 1
fi
if [ ! -d "$SRC/public/plugins/xiaoduiyou-openclaw-connector" ]; then
  echo "Missing source OpenClaw connector: $SRC/public/plugins/xiaoduiyou-openclaw-connector" >&2
  exit 1
fi
if [ ! -d "$SRC/public/skills/xiaoduiyou-usage-workflow" ]; then
  echo "Missing source usage skill: $SRC/public/skills/xiaoduiyou-usage-workflow" >&2
  exit 1
fi

mkdir -p "$DST/plugins" "$DST/skills"
rm -rf \
  "$DST/plugins/xiaoduiyou-platform" \
  "$DST/plugins/xiaoduiyou-openclaw-connector" \
  "$DST/skills/xiaoduiyou-usage-workflow"

cp -R "$SRC/public/plugins/xiaoduiyou-platform" "$DST/plugins/xiaoduiyou-platform"
cp -R "$SRC/public/plugins/xiaoduiyou-openclaw-connector" "$DST/plugins/xiaoduiyou-openclaw-connector"
cp -R "$SRC/public/skills/xiaoduiyou-usage-workflow" "$DST/skills/xiaoduiyou-usage-workflow"

find "$DST/plugins" "$DST/skills" -name '*.zip' -delete

SOURCE_COMMIT=$(git -C "$SRC" rev-parse HEAD)
SOURCE_SHORT=$(git -C "$SRC" rev-parse --short HEAD)
cat > "$DST/manifest.json" <<JSON
{
  "name": "xiaoduiyou-public",
  "source_project": "xiaoduiyou-app",
  "source_commit": "$SOURCE_COMMIT",
  "source_short_commit": "$SOURCE_SHORT",
  "packages": {
    "hermes_plugin": "plugins/xiaoduiyou-platform/xiaoduiyou_platform",
    "openclaw_connector": "plugins/xiaoduiyou-openclaw-connector",
    "usage_skill": "skills/xiaoduiyou-usage-workflow"
  }
}
JSON

echo "Synced Xiaoduiyou public packages from app repo @ $SOURCE_SHORT"
