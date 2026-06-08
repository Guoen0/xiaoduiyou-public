#!/usr/bin/env bash
set -euo pipefail

XDY_PUBLIC_REPO="${XDY_PUBLIC_REPO:-https://github.com/Guoen0/xiaoduiyou-public.git}"
XDY_OPENCLAW_AGENT_INDEX="${XDY_OPENCLAW_AGENT_INDEX:-0}"
OPENCLAW_HOME_DIR="${OPENCLAW_HOME:-${HOME}/.openclaw}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$script_dir/.." && pwd)"
workspace_dir="${OPENCLAW_HOME_DIR}/workspace"

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required environment variable: $name" >&2
    exit 2
  fi
}

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing required command: $name" >&2
    exit 2
  fi
}

require_env XDY_BASE_URL
require_env XDY_CONNECTION_TOKEN
require_cmd git
require_cmd node
require_cmd openclaw

if [ "$repo_dir" = "$workspace_dir" ] || [[ "$repo_dir" == "$workspace_dir"/* ]]; then
  echo "Refusing to update from inside ${OPENCLAW_HOME_DIR}/workspace; use a dedicated clone such as ${OPENCLAW_HOME_DIR}/vendor/xiaoduiyou-public." >&2
  exit 2
fi

if git -C "$repo_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ "${XDY_SKIP_REPO_UPDATE:-0}" != "1" ]; then
    git -C "$repo_dir" fetch origin main
    git -C "$repo_dir" reset --hard origin/main
    git -C "$repo_dir" clean -fd
  fi
fi

for skill in xiaoduiyou-im xiaoduiyou-doc-content-package xiaoduiyou-growth-diary; do
  OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw skills install "$repo_dir/skills/$skill" --as "$skill" --force
done

OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw skills uninstall xiaoduiyou-usage-workflow >/dev/null 2>&1 || true
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw config set "agents.list[$XDY_OPENCLAW_AGENT_INDEX].skills" '["xiaoduiyou-im","xiaoduiyou-doc-content-package","xiaoduiyou-growth-diary"]' --strict-json
tools_also_allow="$(
  OPENCLAW_HOME="$OPENCLAW_HOME_DIR" node - <<'NODE'
const fs = require('node:fs');
const path = `${process.env.OPENCLAW_HOME || `${process.env.HOME}/.openclaw`}/openclaw.json`;
let current = [];
try {
  const config = JSON.parse(fs.readFileSync(path, 'utf8'));
  if (Array.isArray(config?.tools?.alsoAllow)) current = config.tools.alsoAllow;
} catch {
}
const merged = [...new Set([...current.filter((item) => typeof item === 'string'), 'group:plugins'])];
process.stdout.write(JSON.stringify(merged));
NODE
)"
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw config set tools.alsoAllow "$tools_also_allow" --strict-json
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw plugins install "$repo_dir/plugins/xiaoduiyou-openclaw-connector" --force
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw config set channels.xiaoduiyou.enabled true
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw config set channels.xiaoduiyou.baseUrl "$XDY_BASE_URL"
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw config set channels.xiaoduiyou.connectionToken "$XDY_CONNECTION_TOKEN"
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw config set channels.xiaoduiyou.allowFrom '["*"]'
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw gateway restart

OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw skills info xiaoduiyou-im >/dev/null
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw skills info xiaoduiyou-doc-content-package >/dev/null
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw skills info xiaoduiyou-growth-diary >/dev/null
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw plugins list | grep -i xiaoduiyou >/dev/null
OPENCLAW_HOME="$OPENCLAW_HOME_DIR" openclaw config get tools.alsoAllow | grep -F 'group:plugins' >/dev/null
grep -F 'xiaoduiyou_im_send' "$repo_dir/plugins/xiaoduiyou-openclaw-connector/openclaw.plugin.json" >/dev/null
grep -F 'xiaoduiyou_im_send' "$repo_dir/plugins/xiaoduiyou-openclaw-connector/src/tools.js" >/dev/null

echo "Xiaoduiyou OpenClaw connector and skills are installed in ${OPENCLAW_HOME_DIR}."
