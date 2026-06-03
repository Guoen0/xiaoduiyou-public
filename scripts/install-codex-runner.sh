#!/usr/bin/env bash
set -euo pipefail

if [ -z "${XDY_BASE_URL:-}" ] || [ -z "${XDY_CONNECTION_TOKEN:-}" ]; then
  echo "XDY_BASE_URL and XDY_CONNECTION_TOKEN are required" >&2
  exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI is required. Install and sign in to Codex first." >&2
  exit 1
fi
export XDY_CODEX_BIN="$(command -v codex)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLIC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
RUNNER_HOME="$CODEX_HOME/xiaoduiyou-runner"
RUNNER_SCRIPT="$RUNNER_HOME/xiaoduiyou_codex_runner.py"
PLATFORM_PLUGIN_SRC="$PUBLIC_DIR/plugins/xiaoduiyou-codex-platform"
RUNNER_PLUGIN_SRC="$PUBLIC_DIR/plugins/xiaoduiyou-codex-runner"
PERSONAL_MARKETPLACE="$HOME/.agents/plugins/marketplace.json"
PERSONAL_PLUGIN_DIR="$HOME/plugins"

mkdir -p "$RUNNER_HOME" "$PERSONAL_PLUGIN_DIR" "$(dirname "$PERSONAL_MARKETPLACE")"
cp "$RUNNER_PLUGIN_SRC/scripts/xiaoduiyou_codex_runner.py" "$RUNNER_SCRIPT"
chmod +x "$RUNNER_SCRIPT"

python3 "$RUNNER_SCRIPT" configure >/dev/null

if [ ! -f "$PERSONAL_MARKETPLACE" ]; then
  cat > "$PERSONAL_MARKETPLACE" <<'JSON'
{
  "name": "personal",
  "interface": {
    "displayName": "Personal"
  },
  "plugins": []
}
JSON
fi

python3 - "$PERSONAL_MARKETPLACE" "$PERSONAL_PLUGIN_DIR" "$PLATFORM_PLUGIN_SRC" "$RUNNER_PLUGIN_SRC" <<'PY'
import json
import shutil
import sys
from pathlib import Path

marketplace = Path(sys.argv[1])
plugin_dir = Path(sys.argv[2])
sources = [Path(sys.argv[3]), Path(sys.argv[4])]
payload = json.loads(marketplace.read_text(encoding="utf-8"))
payload.setdefault("name", "personal")
payload.setdefault("interface", {"displayName": "Personal"})
payload.setdefault("plugins", [])

for source in sources:
    target = plugin_dir / source.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    entry = {
        "name": source.name,
        "source": {"source": "local", "path": f"./plugins/{source.name}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    payload["plugins"] = [item for item in payload["plugins"] if item.get("name") != source.name]
    payload["plugins"].append(entry)

marketplace.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

codex plugin add xiaoduiyou-codex-platform@personal >/dev/null
codex plugin add xiaoduiyou-codex-runner@personal >/dev/null

if [ "$(uname -s)" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.xiaoduiyou.codex-runner.plist"
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.xiaoduiyou.codex-runner</string>
  <key>ProgramArguments</key>
  <array>
    <string>$RUNNER_SCRIPT</string>
    <string>run</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$RUNNER_HOME/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$RUNNER_HOME/launchd.err.log</string>
</dict>
</plist>
PLIST
  launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  launchctl kickstart -k "gui/$(id -u)/com.xiaoduiyou.codex-runner"
  echo "Installed and started LaunchAgent: $PLIST"
else
  nohup "$RUNNER_SCRIPT" run >>"$RUNNER_HOME/nohup.log" 2>&1 &
  echo "Started runner with nohup: $RUNNER_SCRIPT run"
fi

"$RUNNER_SCRIPT" status
