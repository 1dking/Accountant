#!/bin/bash
# deploy.sh — Reproducible deployment script for DreamHost VPS
# Usage: ssh dh_pjj4dt@vps18033.dreamhostps.com 'cd ~/Accountant && bash deploy.sh'
set -e  # fail on any error

echo "=== $(date) === Starting deployment ==="

echo ">>> Pulling latest code"
git pull origin main

echo ">>> Installing backend dependencies"
cd backend
pip install -r requirements.txt --break-system-packages --quiet 2>/dev/null
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

echo ">>> Restarting backend"
bash stop.sh 2>/dev/null || true
bash start.sh

echo ">>> Waiting for backend to start"
sleep 3

echo ">>> Health check"
if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
    echo "Health check PASSED"
else
    echo "Health check FAILED — backend may not be running"
    tail -20 backend/uvicorn.log
    exit 1
fi

echo "=== $(date) === Deployment complete ==="
