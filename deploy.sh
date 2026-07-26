#!/bin/bash
# deploy.sh — Reproducible deployment script for DreamHost VPS
#
# Usage (pull FIRST, then run — see why below):
#   ssh dh_pjj4dt@vps18033.dreamhostps.com \
#     'cd ~/Accountant && git pull origin main && bash deploy.sh'
#
# Why pull outside the script: bash reads a script incrementally by byte offset,
# so the `git pull` below can rewrite THIS FILE mid-execution. If the pull
# changes deploy.sh's length, bash resumes at a now-wrong offset and can execute
# garbage or skip steps. Pulling first means bash is already running the final
# version and the pull below is a no-op. (Left in place so the script is still
# correct when run standalone.)
set -e  # fail on any error

echo "=== $(date) === Starting deployment ==="

echo ">>> Pulling latest code"
git pull origin main

echo ">>> Installing backend dependencies"
cd backend
# pyproject.toml declares the dependency RANGES and installs the app package.
.venv/bin/pip install -e . --quiet
# Then enforce the PINNED lockfile. This second step is load-bearing for
# security, not redundant: pyproject uses `>=` ranges, so `pip install -e .`
# leaves an already-installed (possibly vulnerable) version in place because it
# still satisfies the range. Without this, the versions CI scans in
# requirements.txt are NOT the versions running in production — which is exactly
# what happened on 2026-07-26: a deploy of the 12-CVE patch left prod on all 12
# vulnerable versions until they were installed by hand.
# Keep requirements.txt in step with reality (see its header for how to regenerate).
.venv/bin/pip install -r requirements.txt --quiet
cd ..

echo ">>> Backing up database before migrations"
# Migrations can rewrite data in place (e.g. the Plaid at-rest encryption
# migration). Snapshot first so a bad migration is recoverable. Non-fatal: a
# backup hiccup shouldn't block an otherwise-fine deploy, but it's loud.
bash scripts/backup.sh || echo "WARNING: pre-migration backup failed — continuing"

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
