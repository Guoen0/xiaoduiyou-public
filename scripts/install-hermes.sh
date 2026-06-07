#!/usr/bin/env bash
set -euo pipefail

XDY_PUBLIC_REPO="${XDY_PUBLIC_REPO:-https://github.com/Guoen0/xiaoduiyou-public.git}"
HERMES_HOME_DIR="${HERMES_HOME:-${HOME}/.hermes}"

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
require_cmd python3
require_cmd rsync

clear_legacy_hermes_env_overrides() {
  local env_file="${HERMES_HOME_DIR}/.env"
  if [ ! -f "$env_file" ]; then
    return
  fi
  local backup_file="${env_file}.bak-xiaoduiyou-$(date +%Y%m%d%H%M%S)"
  cp "$env_file" "$backup_file"
  python3 - "$env_file" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
keys = ("XIAODUIYOU_BASE_URL", "XIAODUIYOU_CONNECTION_TOKEN")
lines = path.read_text(encoding="utf-8").splitlines()
changed = False
next_lines = []
for line in lines:
    stripped = line.lstrip()
    if not stripped.startswith("#") and any(stripped.startswith(f"{key}=") for key in keys):
        next_lines.append(f"# Disabled by xiaoduiyou install-hermes.sh; values are stored in config.yaml: {line}")
        changed = True
    else:
        next_lines.append(line)
if changed:
    path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
PY
  if ! cmp -s "$env_file" "$backup_file"; then
    echo "Disabled legacy Xiaoduiyou overrides in ${env_file}; backup: ${backup_file}"
  else
    rm -f "$backup_file"
  fi
}

write_hermes_connection_token() {
  local config_file="${HERMES_HOME_DIR}/config.yaml"
  mkdir -p "$(dirname "$config_file")"
  touch "$config_file"
  python3 - "$config_file" "$XDY_CONNECTION_TOKEN" <<'PY'
from pathlib import Path
import json
import re
import sys

path = Path(sys.argv[1])
token = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()

def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))

def is_key(line: str, key: str) -> bool:
    stripped = line.strip()
    return bool(stripped and not stripped.startswith("#") and re.match(rf"^{re.escape(key)}\s*:", stripped))

def block_end(start: int) -> int:
    parent_indent = indent_of(lines[start])
    index = start + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped and not stripped.startswith("#") and indent_of(lines[index]) <= parent_indent:
            break
        index += 1
    return index

def find_child(start: int, end: int, key: str) -> int:
    parent_indent = indent_of(lines[start])
    for index in range(start + 1, end):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if indent_of(lines[index]) == parent_indent + 2 and is_key(lines[index], key):
            return index
    return -1

def find_top_key(key: str) -> int:
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if indent_of(line) == 0 and is_key(line, key):
            return index
    return -1

quoted_token = json.dumps(token, ensure_ascii=False)

platforms_index = find_top_key("platforms")
if platforms_index < 0:
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend(["platforms:", "  xiaoduiyou:", "    extra:", f"      connection_token: {quoted_token}"])
else:
    platforms_end = block_end(platforms_index)
    xiaoduiyou_index = find_child(platforms_index, platforms_end, "xiaoduiyou")
    if xiaoduiyou_index < 0:
        lines[platforms_end:platforms_end] = ["  xiaoduiyou:", "    extra:", f"      connection_token: {quoted_token}"]
    else:
        xiaoduiyou_end = block_end(xiaoduiyou_index)
        extra_index = find_child(xiaoduiyou_index, xiaoduiyou_end, "extra")
        if extra_index < 0:
            lines[xiaoduiyou_end:xiaoduiyou_end] = ["    extra:", f"      connection_token: {quoted_token}"]
        else:
            extra_end = block_end(extra_index)
            token_index = find_child(extra_index, extra_end, "connection_token")
            if token_index < 0:
                lines[extra_end:extra_end] = [f"      connection_token: {quoted_token}"]
            else:
                lines[token_index] = f"{' ' * indent_of(lines[token_index])}connection_token: {quoted_token}"

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

if git -C "$repo_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ "${XDY_SKIP_REPO_UPDATE:-0}" != "1" ]; then
    git -C "$repo_dir" fetch origin main
    git -C "$repo_dir" reset --hard origin/main
    git -C "$repo_dir" clean -fd
  fi
fi

mkdir -p "${HERMES_HOME_DIR}/plugins/xiaoduiyou_hermes_platform"
rsync -a --delete "$repo_dir/plugins/xiaoduiyou-hermes-platform/xiaoduiyou_hermes_platform/" "${HERMES_HOME_DIR}/plugins/xiaoduiyou_hermes_platform/"

clear_legacy_hermes_env_overrides

HERMES_HOME="$HERMES_HOME_DIR" hermes config set plugins.enabled '["xiaoduiyou-hermes-platform"]'
HERMES_HOME="$HERMES_HOME_DIR" hermes config set platforms.xiaoduiyou.enabled true
HERMES_HOME="$HERMES_HOME_DIR" hermes config set platforms.xiaoduiyou.extra.base_url "$XDY_BASE_URL"
write_hermes_connection_token
HERMES_HOME="$HERMES_HOME_DIR" hermes config set platforms.xiaoduiyou.extra.poll_interval_seconds 1.0
HERMES_HOME="$HERMES_HOME_DIR" hermes config set platforms.xiaoduiyou.home_channel.platform xiaoduiyou
HERMES_HOME="$HERMES_HOME_DIR" hermes config set platforms.xiaoduiyou.home_channel.chat_id xiaoduiyou
HERMES_HOME="$HERMES_HOME_DIR" hermes config set platforms.xiaoduiyou.home_channel.name Xiaoduiyou
HERMES_HOME="$HERMES_HOME_DIR" hermes config set platform_toolsets.xiaoduiyou '["web","browser","terminal","file","code_execution","vision","image_gen","tts","skills","todo","memory","session_search","clarify","delegation","cronjob","messaging","xiaoduiyou"]'
HERMES_HOME="$HERMES_HOME_DIR" hermes gateway restart

echo "Xiaoduiyou Hermes plugin is installed in ${HERMES_HOME_DIR}."
