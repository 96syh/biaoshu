#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
API_URL="${REACT_APP_API_URL:-http://$BACKEND_HOST:$BACKEND_PORT}"
FRONTEND_URL="http://$FRONTEND_HOST:$FRONTEND_PORT"
HEALTH_URL="http://$BACKEND_HOST:$BACKEND_PORT/health"
OPEN_BROWSER="${OPEN_BROWSER:-1}"
AUTO_INSTALL="${AUTO_INSTALL:-1}"

LOG_DIR="${TMPDIR:-/tmp}/yibiao-simple-dev"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '[yibiao] %s\n' "$*"
}

fail() {
  printf '[yibiao] ERROR: %s\n' "$*" >&2
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

http_ok() {
  curl -fsS "$1" >/dev/null 2>&1
}

port_pids() {
  local port="$1"
  if command_exists lsof; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
  fi
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local log_file="$3"
  local seconds="${4:-60}"
  local i

  for ((i = 1; i <= seconds; i += 1)); do
    if http_ok "$url"; then
      log "$name is ready: $url"
      return 0
    fi
    sleep 1
  done

  printf '\n[yibiao] Last log lines for %s:\n' "$name" >&2
  tail -n 80 "$log_file" >&2 || true
  fail "$name did not become ready within ${seconds}s: $url"
}

cleanup() {
  local exit_code=$?

  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "Stopping frontend process $FRONTEND_PID"
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Stopping backend process $BACKEND_PID"
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  exit "$exit_code"
}

trap cleanup EXIT INT TERM

select_python() {
  if [ -x "$ROOT_DIR/.venv311/bin/python" ]; then
    printf '%s\n' "$ROOT_DIR/.venv311/bin/python"
    return 0
  fi

  if [ -x "/opt/anaconda3/bin/python" ]; then
    printf '%s\n' "/opt/anaconda3/bin/python"
    return 0
  fi

  if command_exists python3; then
    command -v python3
    return 0
  fi

  return 1
}

check_backend_deps() {
  local python_bin="$1"
  if "$python_bin" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    return 0
  fi

  if [ "$AUTO_INSTALL" != "1" ]; then
    fail "backend dependencies are missing for $python_bin. Run: '$python_bin' -m pip install -r '$BACKEND_DIR/requirements.txt'"
  fi

  [ -f "$BACKEND_DIR/requirements.txt" ] || fail "backend requirements file not found: $BACKEND_DIR/requirements.txt"
  log "Backend dependencies are missing; installing backend/requirements.txt"
  "$python_bin" -m pip install -r "$BACKEND_DIR/requirements.txt"
  "$python_bin" -c "import fastapi, uvicorn" >/dev/null 2>&1 || {
    fail "backend dependencies are still unavailable after install for $python_bin"
  }
}

check_frontend_deps() {
  command_exists npm || fail "npm is not installed or not on PATH."
  if [ -d "$FRONTEND_DIR/node_modules" ]; then
    return 0
  fi

  if [ "$AUTO_INSTALL" != "1" ]; then
    fail "frontend dependencies are missing. Run: cd '$FRONTEND_DIR' && npm install"
  fi

  log "Frontend dependencies are missing; running npm install"
  (
    cd "$FRONTEND_DIR"
    npm install
  )
}

start_backend() {
  local python_bin="$1"
  local pids
  pids="$(port_pids "$BACKEND_PORT")"

  if [ -n "$pids" ]; then
    if http_ok "$HEALTH_URL"; then
      log "Backend already running on $HEALTH_URL; reusing existing process."
      return 0
    fi
    fail "port $BACKEND_PORT is already in use by PID(s): $pids"
  fi

  : > "$BACKEND_LOG"
  (
    cd "$BACKEND_DIR"
    if [ -f ".env" ]; then
      set -a
      # shellcheck disable=SC1091
      . "./.env"
      set +a
    fi
    HOST="$BACKEND_HOST" PORT="$BACKEND_PORT" WORKERS=1 "$python_bin" run.py
  ) >>"$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!

  log "Started backend PID $BACKEND_PID on http://$BACKEND_HOST:$BACKEND_PORT"
  wait_for_url "backend" "$HEALTH_URL" "$BACKEND_LOG" 60
}

start_frontend() {
  local pids
  pids="$(port_pids "$FRONTEND_PORT")"

  if [ -n "$pids" ]; then
    if http_ok "$FRONTEND_URL"; then
      log "Frontend already running on $FRONTEND_URL; reusing existing process."
      return 0
    fi
    fail "port $FRONTEND_PORT is already in use by PID(s): $pids"
  fi

  : > "$FRONTEND_LOG"
  (
    cd "$FRONTEND_DIR"
    HOST="$FRONTEND_HOST" \
      PORT="$FRONTEND_PORT" \
      REACT_APP_API_URL="$API_URL" \
      BROWSER=none \
      npm run start
  ) >>"$FRONTEND_LOG" 2>&1 &
  FRONTEND_PID=$!

  log "Started frontend PID $FRONTEND_PID on $FRONTEND_URL"
  wait_for_url "frontend" "$FRONTEND_URL" "$FRONTEND_LOG" 120
}

open_frontend() {
  if [ "$OPEN_BROWSER" != "1" ]; then
    return 0
  fi

  if command_exists open; then
    open "$FRONTEND_URL" >/dev/null 2>&1 || true
  elif command_exists xdg-open; then
    xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true
  fi
}

monitor_children() {
  log "Frontend URL: $FRONTEND_URL"
  log "Backend URL:  http://$BACKEND_HOST:$BACKEND_PORT"
  log "API URL used by frontend: $API_URL"
  log "Logs: $LOG_DIR"
  log "Press Ctrl+C to stop processes started by this script."

  while true; do
    if [ -n "$BACKEND_PID" ] && ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      tail -n 80 "$BACKEND_LOG" >&2 || true
      fail "backend process exited unexpectedly."
    fi

    if [ -n "$FRONTEND_PID" ] && ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
      tail -n 80 "$FRONTEND_LOG" >&2 || true
      fail "frontend process exited unexpectedly."
    fi

    sleep 2
  done
}

main() {
  mkdir -p "$LOG_DIR"
  command_exists curl || fail "curl is not installed or not on PATH."

  local python_bin
  python_bin="$(select_python)" || fail "no Python interpreter found."

  log "Project root: $ROOT_DIR"
  log "Using Python: $python_bin"
  log "Fixed ports: backend=$BACKEND_PORT frontend=$FRONTEND_PORT"
  log "Auto install missing dependencies: $AUTO_INSTALL"

  check_backend_deps "$python_bin"
  check_frontend_deps
  start_backend "$python_bin"
  start_frontend
  open_frontend
  monitor_children
}

main "$@"
