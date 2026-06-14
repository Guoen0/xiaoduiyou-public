#!/usr/bin/env bash
set -euo pipefail

XDY_PUBLIC_REPO="${XDY_PUBLIC_REPO:-https://github.com/Guoen0/xiaoduiyou-public.git}"
HERMES_HOME_DIR="${HERMES_HOME:-${HOME}/.hermes}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$script_dir/.." && pwd)"

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing required command: $name" >&2
    exit 2
  fi
}

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

write_hermes_config() {
  local config_file="${HERMES_HOME_DIR}/config.yaml"
  mkdir -p "$(dirname "$config_file")"
  touch "$config_file"
  cp "$config_file" "${config_file}.bak-xiaoduiyou-$(date +%Y%m%d%H%M%S)"
  python3 - "$config_file" "${XDY_BASE_URL:-}" "${XDY_CONNECTION_TOKEN:-}" <<'PY'
from pathlib import Path
import json
import re
import sys

path = Path(sys.argv[1])
base_url = sys.argv[2].strip()
token = sys.argv[3].strip()
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
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        current_indent = indent_of(lines[index])
        # YAML permits sequence items at the same indent as the key when the
        # key has no inline value, e.g.:
        #   enabled:
        #   - plugin-name
        # Treat those as part of the child block; otherwise replacement leaves
        # stale list items behind and can corrupt config.yaml.
        if current_indent < parent_indent:
            break
        if current_indent == parent_indent and not stripped.startswith("-"):
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
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if indent_of(line) == 0 and is_key(line, key):
            return index
    return -1

def ensure_top_key(key: str) -> int:
    index = find_top_key(key)
    if index >= 0:
        return index
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(f"{key}:")
    return len(lines) - 1

def replace_direct_child(parent_index: int, key: str, child_lines: list[str]) -> int:
    parent_end = block_end(parent_index)
    child_index = find_child(parent_index, parent_end, key)
    if child_index < 0:
        lines[parent_end:parent_end] = child_lines
        return parent_end
    child_end = block_end(child_index)
    lines[child_index:child_end] = child_lines
    return child_index

def yaml_list_block(key: str, values: list[str], indent: int) -> list[str]:
    prefix = " " * indent
    item_prefix = " " * (indent + 2)
    return [f"{prefix}{key}:"] + [f"{item_prefix}- {value}" for value in values]

def scalar_value(line: str, key: str) -> str:
    stripped = line.strip()
    match = re.match(rf"^{re.escape(key)}\s*:\s*(.*)$", stripped)
    if not match:
        return ""
    value = match.group(1).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return value

def find_nested_scalar(path_keys: list[str]) -> str:
    if not path_keys:
        return ""
    current = find_top_key(path_keys[0])
    if current < 0:
        return ""
    for key in path_keys[1:-1]:
        end = block_end(current)
        current = find_child(current, end, key)
        if current < 0:
            return ""
    end = block_end(current)
    leaf = find_child(current, end, path_keys[-1])
    if leaf < 0:
        return ""
    return scalar_value(lines[leaf], path_keys[-1])

if not base_url:
    base_url = find_nested_scalar(["platforms", "xiaoduiyou", "extra", "base_url"])
if not base_url:
    print("Missing XDY_BASE_URL and no existing platforms.xiaoduiyou.extra.base_url found in config.yaml", file=sys.stderr)
    sys.exit(2)

if not token:
    token = find_nested_scalar(["platforms", "xiaoduiyou", "extra", "connection_token"])
if not token:
    # Backward-compatible fallback for older configs that had the token in the
    # Xiaoduiyou block but not under the current exact nesting.
    match = re.search(r'(?m)^\s*connection_token:\s*["\']?([^"\'\n]+)', "\n".join(lines))
    token = match.group(1).strip() if match else ""
if not token:
    print("Missing XDY_CONNECTION_TOKEN and no existing platforms.xiaoduiyou.extra.connection_token found in config.yaml", file=sys.stderr)
    sys.exit(2)

toolsets = [
    "web",
    "browser",
    "terminal",
    "file",
    "code_execution",
    "vision",
    "image_gen",
    "tts",
    "skills",
    "todo",
    "memory",
    "session_search",
    "clarify",
    "delegation",
    "cronjob",
    "messaging",
    "xiaoduiyou",
]

plugins_index = ensure_top_key("plugins")
replace_direct_child(plugins_index, "enabled", yaml_list_block("enabled", ["xiaoduiyou-hermes-platform"], 2))

platforms_index = ensure_top_key("platforms")
replace_direct_child(platforms_index, "xiaoduiyou", [
    "  xiaoduiyou:",
    "    enabled: true",
    "    extra:",
    f"      base_url: {json.dumps(base_url, ensure_ascii=False)}",
    f"      connection_token: {json.dumps(token, ensure_ascii=False)}",
    "      poll_interval_seconds: 1.0",
    "    home_channel:",
    "      platform: xiaoduiyou",
    "      chat_id: xiaoduiyou",
    "      name: 主对话",
])

toolsets_index = ensure_top_key("platform_toolsets")
replace_direct_child(toolsets_index, "xiaoduiyou", yaml_list_block("xiaoduiyou", toolsets, 2))

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

install_hermes_runtime_skills() {
  local skills_dir="${HERMES_HOME_DIR}/skills/xiaoduiyou"
  local legacy_skills_dir="${HERMES_HOME_DIR}/skills/productivity"
  mkdir -p "$skills_dir"
  for skill in xiaoduiyou-im xiaoduiyou-doc-content-package xiaoduiyou-growth-diary; do
    rsync -a --delete "$repo_dir/skills/$skill/" "$skills_dir/$skill/"
    rm -rf "$legacy_skills_dir/$skill"
  done
  rmdir "$legacy_skills_dir" >/dev/null 2>&1 || true
}

restart_hermes_gateway() {
  if [ "${XDY_RESTART_HERMES:-1}" = "0" ]; then
    echo "Skipped Hermes Gateway restart because XDY_RESTART_HERMES=0."
    return
  fi

  local hermes_bin
  hermes_bin="$(command -v hermes)"

  if [ "${_HERMES_GATEWAY:-}" = "1" ]; then
    local restart_log="${HERMES_HOME_DIR}/logs/xiaoduiyou-plugin-upgrade-restart.log"
    mkdir -p "$(dirname "$restart_log")"
    python3 - "$hermes_bin" "$HERMES_HOME_DIR" "$restart_log" <<'PY'
import os
import subprocess
import sys

hermes_bin, hermes_home, restart_log = sys.argv[1:4]
env = os.environ.copy()
env.pop("_HERMES_GATEWAY", None)
env["HERMES_HOME"] = hermes_home
command = (
    "sleep 1; "
    "printf '\\n=== xiaoduiyou plugin upgrade restart %s ===\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\"; "
    "exec \"$1\" gateway restart"
)
with open(restart_log, "a", encoding="utf-8") as log:
    subprocess.Popen(
        ["/bin/sh", "-c", command, "sh", hermes_bin],
        stdout=log,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
        close_fds=True,
    )
PY
    echo "Scheduled Hermes Gateway restart outside the running gateway process; log: ${restart_log}"
    return
  fi

  HERMES_HOME="$HERMES_HOME_DIR" "$hermes_bin" gateway restart
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
install_hermes_runtime_skills

clear_legacy_hermes_env_overrides

write_hermes_config
restart_hermes_gateway

echo "Xiaoduiyou Hermes plugin and runtime skills are installed in ${HERMES_HOME_DIR}."
