#!/usr/bin/env bash
# ============================================================================
# Accountant — DreamHost Managed VPS Deploy Script (No Sudo Required)
# ============================================================================
# Usage:  SSH into your DreamHost VPS and run:
#   curl -fsSL https://raw.githubusercontent.com/1dking/Accountant/main/deploy.sh -o deploy.sh
#   bash deploy.sh
#
# Works on DreamHost managed VPS where you do NOT have sudo/root access.
# ============================================================================

# Fix Windows CRLF line endings if present
if head -1 "$0" | grep -q $'\r'; then
    sed -i 's/\r$//' "$0"
    exec bash "$0" "$@"
fi

set -euo pipefail

# ---- Colours for output ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

step() { echo -e "\n${BLUE}==>${NC} ${GREEN}$1${NC}"; }
warn() { echo -e "${YELLOW}⚠  $1${NC}"; }
fail() { echo -e "${RED}✗  $1${NC}"; exit 1; }
ok()   { echo -e "${GREEN}✓  $1${NC}"; }

# ---- Gather required values ----
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════╗"
echo "║        Accountant — VPS Deploy Script            ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

VPS_USER=$(whoami)
APP_DIR="/home/${VPS_USER}/Accountant"

read -rp "GitHub repo URL [https://github.com/1dking/Accountant.git]: " REPO_URL
REPO_URL=${REPO_URL:-https://github.com/1dking/Accountant.git}

read -rp "Domain name (e.g. accountant.example.com): " DOMAIN
[[ -z "$DOMAIN" ]] && fail "Domain name is required."

echo ""
echo "Paste your Supabase DATABASE_URL (starts with postgresql://...)"
echo "Find it in: Supabase Dashboard → Settings → Database → Connection string → URI"
read -rp "DATABASE_URL: " SUPABASE_URL
[[ -z "$SUPABASE_URL" ]] && fail "DATABASE_URL is required."

# Convert postgresql:// to postgresql+asyncpg:// for SQLAlchemy async
DB_URL="${SUPABASE_URL/postgresql:\/\//postgresql+asyncpg:\/\/}"

read -rp "Anthropic API key (sk-ant-...): " ANTHROPIC_KEY
[[ -z "$ANTHROPIC_KEY" ]] && fail "Anthropic API key is required."

echo ""
ok "Configuration collected. Starting deployment..."

# ---- 1. Clone repository ----
step "Cloning repository..."
if [[ -d "$APP_DIR" ]]; then
    warn "Directory $APP_DIR already exists — pulling latest..."
    cd "$APP_DIR" && git pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
ok "Repository ready at $APP_DIR"

# ---- 2. Install Node.js via nvm (no sudo needed) ----
step "Setting up Node.js..."
export NVM_DIR="$HOME/.nvm"
if [[ ! -d "$NVM_DIR" ]]; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
# Load nvm
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 20 ]]; then
    nvm install 22
    nvm use 22
fi
ok "Node.js $(node -v)"

# Install pnpm
if ! command -v pnpm &>/dev/null; then
    npm install -g pnpm 2>/dev/null || corepack enable pnpm 2>/dev/null || npm install -g pnpm
fi
ok "pnpm $(pnpm -v)"

# ---- 3. Python virtual environment + dependencies ----
step "Setting up Python backend..."
cd "$APP_DIR/backend"

# Check python3 is available
if ! command -v python3 &>/dev/null; then
    fail "python3 is not installed. Contact DreamHost support to enable Python 3."
fi
ok "Python $(python3 --version)"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q
ok "Python dependencies installed"

# ---- 4. Generate secrets ----
step "Generating secrets..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ok "SECRET_KEY and FERNET_KEY generated"

# ---- 5. Write .env file ----
step "Writing backend .env file..."
cat > "$APP_DIR/backend/.env" <<ENVEOF
# Database (Supabase PostgreSQL)
DATABASE_URL=${DB_URL}

# Auth
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Storage
STORAGE_TYPE=local
STORAGE_PATH=./data/documents
MAX_UPLOAD_SIZE=52428800

# Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=https://${DOMAIN}

# AI
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
ANTHROPIC_MODEL=claude-sonnet-4-20250514
AI_AUTO_EXTRACT=true

# Encryption
FERNET_KEY=${FERNET_KEY}

# Google OAuth (configure later in Settings)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://${DOMAIN}/api/integrations/gmail/callback
ENVEOF
ok ".env written"

# ---- 6. Create data directory ----
mkdir -p "$APP_DIR/backend/data/documents"

# ---- 7. Run database migrations ----
step "Running database migrations..."
cd "$APP_DIR/backend"
source .venv/bin/activate
alembic upgrade head
ok "Database migrated"

# ---- 8. Build frontend ----
step "Building frontend..."
cd "$APP_DIR/frontend"
# Load nvm in case it's not in PATH
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
pnpm install --frozen-lockfile
pnpm build
ok "Frontend built → $APP_DIR/frontend/dist"

# ---- 9. Stop any existing instance ----
step "Starting backend server..."
if [[ -f "$APP_DIR/backend/uvicorn.pid" ]]; then
    OLD_PID=$(cat "$APP_DIR/backend/uvicorn.pid" 2>/dev/null || echo "")
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
        ok "Stopped previous instance (PID $OLD_PID)"
    fi
fi

# ---- 10. Start uvicorn in background ----
cd "$APP_DIR/backend"
source .venv/bin/activate
nohup "$APP_DIR/backend/.venv/bin/uvicorn" app.main:app \
    --host 0.0.0.0 --port 8000 \
    > "$APP_DIR/backend/uvicorn.log" 2>&1 &
UVICORN_PID=$!
echo "$UVICORN_PID" > "$APP_DIR/backend/uvicorn.pid"
ok "uvicorn started (PID $UVICORN_PID)"

# Give it a moment to start
sleep 3

# Verify backend is running
if curl -sf http://127.0.0.1:8000/api/system/health > /dev/null 2>&1; then
    ok "Backend is responding on port 8000"
else
    warn "Backend may still be starting. Check: tail -f $APP_DIR/backend/uvicorn.log"
fi

# ---- 11. Set up cron job for auto-restart on reboot ----
step "Setting up auto-restart cron job..."
CRON_CMD="@reboot cd $APP_DIR/backend && source .venv/bin/activate && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 & echo \$! > uvicorn.pid"

# Add cron job if not already present
(crontab -l 2>/dev/null | grep -v "Accountant/backend" || true; echo "$CRON_CMD") | crontab -
ok "Cron job installed — backend will auto-start on VPS reboot"

# ---- 12. Create helper scripts ----
cat > "$APP_DIR/start.sh" <<'STARTEOF'
#!/usr/bin/env bash
# Start the Accountant backend
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR/backend"

# Stop existing instance
if [[ -f uvicorn.pid ]]; then
    OLD_PID=$(cat uvicorn.pid 2>/dev/null || echo "")
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
        echo "Stopped previous instance"
    fi
fi

source .venv/bin/activate
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
echo $! > uvicorn.pid
echo "Backend started (PID $(cat uvicorn.pid))"
STARTEOF
chmod +x "$APP_DIR/start.sh"

cat > "$APP_DIR/stop.sh" <<'STOPEOF'
#!/usr/bin/env bash
# Stop the Accountant backend
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$APP_DIR/backend/uvicorn.pid" ]]; then
    PID=$(cat "$APP_DIR/backend/uvicorn.pid")
    kill "$PID" 2>/dev/null && echo "Stopped (PID $PID)" || echo "Not running"
    rm -f "$APP_DIR/backend/uvicorn.pid"
else
    echo "No PID file found"
fi
STOPEOF
chmod +x "$APP_DIR/stop.sh"

cat > "$APP_DIR/update.sh" <<'UPDATEEOF'
#!/usr/bin/env bash
# Pull latest code, rebuild, and restart
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Pulling latest code..."
cd "$APP_DIR" && git pull

echo "Updating backend..."
cd "$APP_DIR/backend"
source .venv/bin/activate
pip install -e ".[dev]" -q
alembic upgrade head

echo "Rebuilding frontend..."
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build

echo "Restarting backend..."
"$APP_DIR/stop.sh"
"$APP_DIR/start.sh"

echo "Done! App updated."
UPDATEEOF
chmod +x "$APP_DIR/update.sh"

cat > "$APP_DIR/logs.sh" <<'LOGSEOF'
#!/usr/bin/env bash
# View backend logs
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
tail -f "$APP_DIR/backend/uvicorn.log"
LOGSEOF
chmod +x "$APP_DIR/logs.sh"

# ---- Done! ----
echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║        Server setup complete!                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Backend running at: http://localhost:8000"
echo ""
echo -e "${YELLOW}  ⚡ IMPORTANT — Complete these 2 steps in the DreamHost panel:${NC}"
echo ""
echo "  1. SET UP PROXY:"
echo "     Go to: Servers → your VPS → Proxy Server"
echo "     URL:  accountant.ocidm.io   (leave path blank)"
echo "     Port: 8000"
echo "     Click 'Add Proxy'"
echo ""
echo "  2. ENABLE SSL:"
echo "     Go to: Websites → Secure Certificates"
echo "     Add a free Let's Encrypt certificate for accountant.ocidm.io"
echo ""
echo -e "  Once proxy is active, your app will be live at:"
echo -e "  ${GREEN}https://${DOMAIN}${NC}"
echo ""
echo "  Helper commands:"
echo "    ~/Accountant/start.sh     # Start the backend"
echo "    ~/Accountant/stop.sh      # Stop the backend"
echo "    ~/Accountant/update.sh    # Pull + rebuild + restart"
echo "    ~/Accountant/logs.sh      # View live logs"
echo ""
