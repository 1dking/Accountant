#!/usr/bin/env bash
# Start the Accountant backend + Hocuspocus (real-time Docs collaboration).
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# Stop existing backend
cd "$APP_DIR/backend"
if [[ -f uvicorn.pid ]]; then
    OLD_PID=$(cat uvicorn.pid 2>/dev/null || echo "")
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
        echo "Stopped previous backend instance"
    fi
fi

# Stop existing Hocuspocus
if [[ -f "$APP_DIR/hocuspocus.pid" ]]; then
    OLD_PID=$(cat "$APP_DIR/hocuspocus.pid" 2>/dev/null || echo "")
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
        echo "Stopped previous Hocuspocus instance"
    fi
fi

# Start Hocuspocus (real-time collaboration for Docs). Reached from the
# browser via the /api/collaborate WebSocket proxy in backend/app/main.py
# -- DreamHost only exposes port 8000, not 1234 directly.
cd "$APP_DIR/backend/hocuspocus"
BACKEND_URL=http://127.0.0.1:8000 HOCUSPOCUS_PORT=1234 \
    nohup node server.js > "$APP_DIR/hocuspocus.log" 2>&1 &
echo $! > "$APP_DIR/hocuspocus.pid"
echo "Hocuspocus started (PID $(cat "$APP_DIR/hocuspocus.pid")) on port 1234"

# Start backend
cd "$APP_DIR/backend"
source .venv/bin/activate
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
echo $! > uvicorn.pid
echo "Backend started (PID $(cat uvicorn.pid))"
