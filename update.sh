#!/usr/bin/env bash
# Pull latest code, rebuild, and restart.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

echo "Pulling latest code..."
cd "$APP_DIR" && git pull

echo "Updating backend..."
cd "$APP_DIR/backend"
source .venv/bin/activate
pip install -e ".[dev]" -q
alembic upgrade head

echo "Updating Hocuspocus..."
cd "$APP_DIR/backend/hocuspocus"
npm install --production 2>/dev/null

echo "Rebuilding frontend..."
cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build

echo "Restarting..."
"$APP_DIR/stop.sh"
"$APP_DIR/start.sh"

echo "Done! App updated."
