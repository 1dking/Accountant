#!/bin/bash
# deploy.sh — Reproducible deployment script for DreamHost VPS
# Usage: ssh dh_pjj4dt@vps18033.dreamhostps.com 'cd ~/Accountant && bash deploy.sh'
set -e  # fail on any error

echo "=== $(date) === Starting deployment ==="

echo ">>> Pulling latest code"
git pull origin main

echo ">>> Installing backend dependencies"
cd backend
# Was: `pip install -r requirements.txt --break-system-packages --quiet 2>/dev/null`
# There is no requirements.txt — not in the repo, not on the VPS. pip exited 2,
# and with `set -e` that aborted the whole deploy before migrations, build or
# restart; the `2>/dev/null` hid the reason. Dependencies are declared in
# pyproject.toml and the app runs from .venv (which the alembic step below
# already assumes), so install from there. Idempotent when deps are satisfied.
.venv/bin/pip install -e . --quiet
cd ..

echo ">>> Running database migrations"
cd backend
.venv/bin/alembic upgrade head
cd ..

echo ">>> Building frontend"
cd frontend
pnpm install --frozen-lockfile --silent
pnpm run build
cd ..

echo ">>> Installing Hocuspocus dependencies"
cd backend/hocuspocus
npm install --production --quiet 2>/dev/null || npm install --production
cd ../..

echo ">>> Restarting backend + Hocuspocus"
bash stop.sh 2>/dev/null || true
bash start.sh

echo ">>> Waiting for backend to start"
# Poll instead of sleeping a fixed 3s. Startup does template + platform-admin
# seeding and takes longer than that, so the old fixed sleep reported
# "Health check FAILED" on deploys that had in fact succeeded — a false alarm
# that makes a real failure indistinguishable from a slow boot.
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
        HEALTHY=true
        echo "Backend healthy after ${i}s"
        break
    fi
    sleep 1
done

echo ">>> Health check"
if [ "$HEALTHY" = true ]; then
    echo "Health check PASSED"
else
    echo "Health check FAILED — backend did not come up within 30s"
    tail -20 backend/uvicorn.log
    exit 1
fi

# Non-fatal: Hocuspocus (real-time Docs collaboration) is optional --
# DocEditorPage.tsx falls back to REST autosave if it's unreachable, so a
# down collaboration server degrades a feature, it doesn't break editing.
if curl -sf http://localhost:1234/ > /dev/null 2>&1; then
    echo "Hocuspocus healthy"
else
    echo "WARNING: Hocuspocus did not come up — real-time collaboration will be unavailable (editing still works via autosave)"
    tail -20 hocuspocus.log 2>/dev/null || true
fi

echo "=== $(date) === Deployment complete ==="
