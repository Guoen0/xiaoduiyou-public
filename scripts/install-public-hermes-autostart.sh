#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_SCRIPT="$ROOT/scripts/start-public-hermes-gateway.sh"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
TARGET_SCRIPT="$HERMES_HOME_DIR/scripts/start-public-agent-gateway.sh"
STARTUP_TARGET="${XDY_SEALOS_STARTUP_SCRIPT:-/usr/start/startup.sh}"

usage() {
  cat <<'USAGE'
Usage: scripts/install-public-hermes-autostart.sh

Installs the maintainer-only production public Hermes gateway startup hook for
Sealos Devbox. It preserves the existing Xiaoduiyou base_url/token in
HERMES_HOME/config.yaml and does not print secrets.
USAGE
}

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif sudo -n true >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

harden_startup_script() {
  local startup="$1"
  local tmp
  tmp="/tmp/xdy-public-hermes-startup-harden.$$"
  python3 - "$startup" > "$tmp" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

text = text.replace(
    '    echo "${SEALOS_DEVBOX_NAME}">/etc/hostname',
    '    { echo "${SEALOS_DEVBOX_NAME}" >/etc/hostname; } 2>/dev/null || true',
)
text = text.replace(
    'echo "${SEALOS_DEVBOX_POD_UID}">/usr/start/pod_id',
    'mkdir -p /usr/start 2>/dev/null || true\n{ echo "${SEALOS_DEVBOX_POD_UID:-}" >/usr/start/pod_id; } 2>/dev/null || true',
)
text = text.replace(
    '# Start the SSH daemon\n/usr/sbin/sshd',
    '# Start the SSH daemon\nif command -v /usr/sbin/sshd >/dev/null 2>&1; then\n    mkdir -p /run/sshd 2>/dev/null || true\n    pgrep -x sshd >/dev/null 2>&1 || /usr/sbin/sshd 2>/dev/null || true\nfi',
)
text = text.replace(
    '/usr/sbin/sshd\nsleep infinity',
    'if command -v /usr/sbin/sshd >/dev/null 2>&1; then\n    mkdir -p /run/sshd 2>/dev/null || true\n    pgrep -x sshd >/dev/null 2>&1 || /usr/sbin/sshd 2>/dev/null || true\nfi\nsleep infinity',
)
print(text, end="")
PY
  run_as_root install -m 0755 "$tmp" "$startup"
  rm -f "$tmp"
}

case "${1:-}" in
  -h|--help|help)
    usage
    exit 0
    ;;
  '')
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

bash -n "$SOURCE_SCRIPT"
mkdir -p "$(dirname "$TARGET_SCRIPT")"
install -m 0700 "$SOURCE_SCRIPT" "$TARGET_SCRIPT"

run_as_root mkdir -p "$(dirname "$STARTUP_TARGET")"
if ! run_as_root test -f "$STARTUP_TARGET"; then
  cat > /tmp/xdy-public-hermes-startup.$$ <<'SCRIPT'
#!/bin/bash

if [ ! -z "${SEALOS_DEVBOX_NAME}" ]; then
    { echo "${SEALOS_DEVBOX_NAME}" >/etc/hostname; } 2>/dev/null || true
fi

mkdir -p /usr/start 2>/dev/null || true
{ echo "${SEALOS_DEVBOX_POD_UID:-}" >/usr/start/pod_id; } 2>/dev/null || true
if command -v /usr/sbin/sshd >/dev/null 2>&1; then
    mkdir -p /run/sshd 2>/dev/null || true
    pgrep -x sshd >/dev/null 2>&1 || /usr/sbin/sshd 2>/dev/null || true
fi
sleep infinity
SCRIPT
  run_as_root install -m 0755 /tmp/xdy-public-hermes-startup.$$ "$STARTUP_TARGET"
  rm -f /tmp/xdy-public-hermes-startup.$$
fi

if ! run_as_root grep -q 'start-public-agent-gateway.sh' "$STARTUP_TARGET"; then
  backup="$STARTUP_TARGET.bak-$(date +%Y%m%d%H%M%S)"
  run_as_root cp "$STARTUP_TARGET" "$backup"
  tmp="/tmp/xdy-public-hermes-startup.$$"
  awk '
    /sleep infinity/ && ! inserted {
      print "# Start Xiaoduiyou production public Hermes gateway if configured."
      print "if [ -x /home/devbox/.hermes/scripts/start-public-agent-gateway.sh ]; then"
      print "    su - devbox -c /home/devbox/.hermes/scripts/start-public-agent-gateway.sh"
      print "fi"
      inserted = 1
    }
    { print }
    END {
      if (!inserted) {
        print "# Start Xiaoduiyou production public Hermes gateway if configured."
        print "if [ -x /home/devbox/.hermes/scripts/start-public-agent-gateway.sh ]; then"
        print "    su - devbox -c /home/devbox/.hermes/scripts/start-public-agent-gateway.sh"
        print "fi"
      }
    }
  ' "$STARTUP_TARGET" > "$tmp"
  run_as_root install -m 0755 "$tmp" "$STARTUP_TARGET"
  rm -f "$tmp"
  echo "backup=$backup"
fi

harden_startup_script "$STARTUP_TARGET"
run_as_root bash -n "$STARTUP_TARGET"
echo "installed_gateway_script=$TARGET_SCRIPT"
echo "installed_startup=$STARTUP_TARGET"
echo "public_hermes_autostart=enabled"
