#!/usr/bin/env bash
# Stop the Accountant backend + Hocuspocus.
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -f "$APP_DIR/backend/uvicorn.pid" ]]; then
    PID=$(cat "$APP_DIR/backend/uvicorn.pid")
    kill "$PID" 2>/dev/null && echo "Stopped backend (PID $PID)" || echo "Backend not running"
    rm -f "$APP_DIR/backend/uvicorn.pid"
else
    echo "Backend: no PID file found"
fi

if [[ -f "$APP_DIR/hocuspocus.pid" ]]; then
    PID=$(cat "$APP_DIR/hocuspocus.pid")
    kill "$PID" 2>/dev/null && echo "Stopped Hocuspocus (PID $PID)" || echo "Hocuspocus not running"
    rm -f "$APP_DIR/hocuspocus.pid"
else
    echo "Hocuspocus: no PID file found"
fi
