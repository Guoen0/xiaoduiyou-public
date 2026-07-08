#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/home/devbox}"
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export PATH="$HOME/.local/bin:$HERMES_HOME/bin:$HERMES_HOME/node/bin:$PATH"
export HERMES_ACCEPT_HOOKS="${HERMES_ACCEPT_HOOKS:-1}"

LOG_FILE="${XDY_PUBLIC_HERMES_GATEWAY_LOG:-$HERMES_HOME/logs/gateway-public-agent.log}"
WATCHDOG_LOG_FILE="${XDY_PUBLIC_HERMES_WATCHDOG_LOG:-$HERMES_HOME/logs/gateway-public-agent-watchdog.log}"
WATCHDOG_INTERVAL_SECONDS="${XDY_PUBLIC_HERMES_WATCHDOG_INTERVAL_SECONDS:-60}"
WATCHDOG_PID_FILE="$HERMES_HOME/gateway-public-agent-watchdog.pid"
GATEWAY_PID_FILE="$HERMES_HOME/gateway-public-agent.pid"

mkdir -p "$HERMES_HOME/logs" "$HERMES_HOME/scripts"

if [ -f "$HERMES_HOME/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$HERMES_HOME/.env"
  set +a
fi

log_watchdog() {
  echo "$(date -Is) $*" >>"$WATCHDOG_LOG_FILE"
}

hermes_cmd() {
  command -v hermes 2>/dev/null || true
}

pid_is_gateway() {
  local pid="$1"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" >/dev/null 2>&1 || return 1
  ps -p "$pid" -o command= 2>/dev/null | grep -E 'hermes.*gateway run|hermes-agent.*gateway run' >/dev/null 2>&1
}

gateway_pid_running() {
  local pid_file pid
  for pid_file in "$GATEWAY_PID_FILE" "$HERMES_HOME/gateway.pid"; do
    [ -f "$pid_file" ] || continue
    pid="$(tr -dc '0-9' < "$pid_file")"
    pid_is_gateway "$pid" && return 0
  done
  return 1
}

gateway_process_running() {
  ps -eo command | grep -E 'hermes.*gateway run|hermes-agent.*gateway run' | grep -v grep >/dev/null 2>&1
}

gateway_running() {
  local bin status
  gateway_pid_running && return 0
  gateway_process_running && return 0
  bin="$(hermes_cmd)"
  [ -n "$bin" ] || return 1
  status="$("$bin" gateway status 2>&1 || true)"
  printf '%s' "$status" | grep -Eq 'Gateway is running|already running'
}

start_gateway() {
  if gateway_running; then
    log_watchdog "gateway already running"
    return 0
  fi

  local bin
  bin="$(hermes_cmd)"
  if [ -z "$bin" ]; then
    log_watchdog "gateway start failed: hermes command not found"
    return 1
  fi

  nohup env HOME="$HOME" HERMES_HOME="$HERMES_HOME" PATH="$PATH" HERMES_ACCEPT_HOOKS="$HERMES_ACCEPT_HOOKS" \
    "$bin" gateway run >>"$LOG_FILE" 2>&1 &
  echo "$!" >"$GATEWAY_PID_FILE"
  log_watchdog "gateway started pid=$!"
}

watch_gateway() {
  echo "$$" >"$WATCHDOG_PID_FILE"
  while true; do
    sleep "$WATCHDOG_INTERVAL_SECONDS"
    if gateway_running; then
      log_watchdog "gateway health ok"
      continue
    fi
    log_watchdog "gateway missing; starting"
    start_gateway || log_watchdog "gateway start failed"
  done
}

watchdog_running() {
  [ -f "$WATCHDOG_PID_FILE" ] || return 1
  local pid
  pid="$(tr -dc '0-9' < "$WATCHDOG_PID_FILE")"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

case "${XDY_PUBLIC_HERMES_STARTUP_MODE:-serve}" in
  once)
    start_gateway
    ;;
  watchdog)
    watch_gateway
    ;;
  serve|'')
    start_gateway
    if ! watchdog_running; then
      nohup env HOME="$HOME" HERMES_HOME="$HERMES_HOME" PATH="$PATH" HERMES_ACCEPT_HOOKS="$HERMES_ACCEPT_HOOKS" \
        XDY_PUBLIC_HERMES_STARTUP_MODE=watchdog "$0" >>"$WATCHDOG_LOG_FILE" 2>&1 &
      echo "$!" >"$WATCHDOG_PID_FILE"
      log_watchdog "watchdog started pid=$!"
    fi
    ;;
  *)
    echo "unknown XDY_PUBLIC_HERMES_STARTUP_MODE=${XDY_PUBLIC_HERMES_STARTUP_MODE}" >&2
    exit 2
    ;;
esac
