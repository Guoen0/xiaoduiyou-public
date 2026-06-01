#!/usr/bin/env bash
set -euo pipefail

XDY_PUBLIC_REPO="${XDY_PUBLIC_REPO:-https://github.com/Guoen0/xiaoduiyou-public.git}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$script_dir/.." && pwd)"

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
require_cmd hermes
require_cmd rsync

if git -C "$repo_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ "${XDY_SKIP_REPO_UPDATE:-0}" != "1" ]; then
    git -C "$repo_dir" fetch origin main
    git -C "$repo_dir" reset --hard origin/main
    git -C "$repo_dir" clean -fd
  fi
fi

mkdir -p "${HOME}/.hermes/plugins/xiaoduiyou_hermes_platform"
rsync -a --delete "$repo_dir/plugins/xiaoduiyou-hermes-platform/xiaoduiyou_hermes_platform/" "${HOME}/.hermes/plugins/xiaoduiyou_hermes_platform/"

hermes config set plugins.enabled '["xiaoduiyou-hermes-platform"]'
hermes config set platforms.xiaoduiyou.enabled true
hermes config set platforms.xiaoduiyou.extra.base_url "$XDY_BASE_URL"
hermes config set platforms.xiaoduiyou.extra.connection_token "$XDY_CONNECTION_TOKEN"
hermes config set platforms.xiaoduiyou.extra.poll_interval_seconds 1.0
hermes config set platforms.xiaoduiyou.home_channel.platform xiaoduiyou
hermes config set platforms.xiaoduiyou.home_channel.chat_id xiaoduiyou
hermes config set platforms.xiaoduiyou.home_channel.name Xiaoduiyou
hermes config set platform_toolsets.xiaoduiyou '["web","browser","terminal","file","code_execution","vision","image_gen","tts","skills","todo","memory","session_search","clarify","delegation","cronjob","messaging","xiaoduiyou"]'
hermes gateway restart

echo "Xiaoduiyou Hermes plugin is installed."
