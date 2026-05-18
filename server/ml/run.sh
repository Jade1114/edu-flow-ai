#!/usr/bin/env bash
# Start FastAPI ML service with all output persisted to logs/uvicorn.log
set -euo pipefail

cd "$(dirname "$0")"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

UVICORN_LOG="$LOG_DIR/uvicorn.log"

echo "Starting FastAPI ML service..."
echo "  Log: $PWD/$UVICORN_LOG"
echo "  PID: $$"

exec .venv/bin/python -m uvicorn api.main:app \
  --host 127.0.0.1 \
  --port 8089 \
  --log-level warning \
  >> "$UVICORN_LOG" 2>&1
