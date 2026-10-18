#!/usr/bin/env bash
# init.sh: start the development server and run a basic end-to-end check.
# Source: Anthropic, Effective harnesses asks for "an init.sh script that can run the development server", then a basic
# end-to-end test before any new work. Every session runs it first.
# Set the four commands below for your repository (or export them before running).
# Output stays short; full logs go to $LOG_DIR (Anthropic, C compiler: print a few lines, log the rest to a file).
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
LOG_DIR="${LOG_DIR:-.init-logs}"
INSTALL_CMD="${INSTALL_CMD:-uv sync}"
SERVER_CMD="${SERVER_CMD:-uv run uvicorn app.main:app --port $PORT}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:$PORT/health}"
SMOKE_CMD="${SMOKE_CMD:-uv run pytest -q -x tests/smoke}"
WAIT_SECONDS="${WAIT_SECONDS:-30}"

mkdir -p "$LOG_DIR"

echo "init: installing dependencies"
if ! bash -c "$INSTALL_CMD" >"$LOG_DIR/install.log" 2>&1; then
  echo "ERROR install failed: see $LOG_DIR/install.log"
  exit 1
fi

if [ -f "$LOG_DIR/server.pid" ] && kill -0 "$(cat "$LOG_DIR/server.pid")" 2>/dev/null; then
  echo "init: stopping the server from the previous run"
  kill "$(cat "$LOG_DIR/server.pid")" || true
fi

echo "init: starting the server on port $PORT"
bash -c "$SERVER_CMD" >"$LOG_DIR/server.log" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" >"$LOG_DIR/server.pid"

healthy=0
for _ in $(seq 1 "$WAIT_SECONDS"); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "ERROR server exited during start: see $LOG_DIR/server.log"
    exit 1
  fi
  sleep 1
done
if [ "$healthy" -ne 1 ]; then
  echo "ERROR server not healthy at $HEALTH_URL after $WAIT_SECONDS s: see $LOG_DIR/server.log"
  exit 1
fi

echo "init: running the smoke test"
if ! bash -c "$SMOKE_CMD" >"$LOG_DIR/smoke.log" 2>&1; then
  echo "ERROR smoke test failed: see $LOG_DIR/smoke.log. Fix this before starting new work."
  exit 1
fi

echo "init: ok (server pid $SERVER_PID, logs in $LOG_DIR/)"
