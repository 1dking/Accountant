#!/usr/bin/env bash
# ============================================================================
# Accountant — DreamHost Managed VPS Deploy Script (No Sudo Required)
# ============================================================================
# Usage:  SSH into your DreamHost VPS and run:
#   curl -fsSL https://raw.githubusercontent.com/1dking/Accountant/main/deploy.sh -o deploy.sh
#   bash deploy.sh
#
# Works on DreamHost managed VPS where you do NOT have sudo/root access.
# Includes: FastAPI backend, React frontend, LiveKit (video), Hocuspocus (collab)
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
echo "║   Backend + LiveKit + Hocuspocus + Frontend      ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

VPS_USER=$(whoami)
APP_DIR="/home/${VPS_USER}/Accountant"

# Use environment variables if set, otherwise prompt
if [[ -z "${REPO_URL:-}" ]]; then
    read -rp "GitHub repo URL [https://github.com/1dking/Accountant.git]: " REPO_URL
fi
REPO_URL=${REPO_URL:-https://github.com/1dking/Accountant.git}

if [[ -z "${DOMAIN:-}" ]]; then
    read -rp "Domain name (e.g. accountant.example.com): " DOMAIN
fi
[[ -z "$DOMAIN" ]] && fail "Domain name is required."

if [[ -z "${SUPABASE_URL:-}" ]]; then
    echo ""
    echo "Paste your Supabase DATABASE_URL (starts with postgresql://...)"
    echo "Find it in: Supabase Dashboard → Settings → Database → Connection string → URI"
    read -rp "DATABASE_URL: " SUPABASE_URL
fi
[[ -z "$SUPABASE_URL" ]] && fail "DATABASE_URL is required."

# Convert postgresql:// to postgresql+asyncpg:// for SQLAlchemy async
DB_URL="${SUPABASE_URL/postgresql:\/\//postgresql+asyncpg:\/\/}"

if [[ -z "${ANTHROPIC_KEY:-}" ]]; then
    read -rp "Anthropic API key (sk-ant-...): " ANTHROPIC_KEY
fi
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

# Create virtual environment
if python3 -m venv .venv 2>/dev/null; then
    ok "Created venv"
else
    warn "python3-venv not available, using standalone virtualenv..."
    curl -fsSL https://bootstrap.pypa.io/virtualenv.pyz -o /tmp/virtualenv.pyz
    python3 /tmp/virtualenv.pyz .venv
    ok "Created virtualenv"
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q
ok "Python dependencies installed"

# ---- 4. Download LiveKit server binary ----
step "Setting up LiveKit (video meetings)..."
mkdir -p "$APP_DIR/bin"

if [[ ! -f "$APP_DIR/bin/livekit-server" ]]; then
    echo "Downloading LiveKit server..."
    LIVEKIT_VERSION="v1.8.3"
    curl -fsSL "https://github.com/livekit/livekit/releases/download/${LIVEKIT_VERSION}/livekit_${LIVEKIT_VERSION#v}_linux_amd64.tar.gz" \
        -o /tmp/livekit.tar.gz
    tar xzf /tmp/livekit.tar.gz -C "$APP_DIR/bin/" livekit-server
    chmod +x "$APP_DIR/bin/livekit-server"
    rm -f /tmp/livekit.tar.gz
    ok "LiveKit server downloaded"
else
    ok "LiveKit server already present"
fi

# Generate LiveKit API key and secret
LIVEKIT_API_KEY="APIKey$(python3 -c "import secrets; print(secrets.token_hex(8))")"
LIVEKIT_API_SECRET="$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")"

# Write LiveKit config
cat > "$APP_DIR/livekit.yaml" <<LKEOF
port: 7880
rtc:
    port_range_start: 50000
    port_range_end: 50200
    use_external_ip: true
    tcp_fallback_port: 7881
keys:
    ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
logging:
    level: info
LKEOF
ok "LiveKit configured (port 7880, RTC 50000-50200, TCP fallback 7881)"

# ---- 5. Set up Hocuspocus (collaboration server) ----
step "Setting up Hocuspocus (real-time collaboration)..."
cd "$APP_DIR/backend/hocuspocus"
npm install --production 2>/dev/null
ok "Hocuspocus dependencies installed"

# ---- 6. Generate secrets ----
step "Generating secrets..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ok "SECRET_KEY and FERNET_KEY generated"

# ---- 7. Write .env file ----
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
MAX_UPLOAD_SIZE=0
RECORDINGS_STORAGE_PATH=./data/recordings

# Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=["https://${DOMAIN}"]

# AI
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
ANTHROPIC_MODEL=claude-sonnet-4-20250514
AI_AUTO_EXTRACT=true

# Encryption
FERNET_KEY=${FERNET_KEY}

# LiveKit (video meetings)
LIVEKIT_URL=wss://${DOMAIN}/livekit/
LIVEKIT_API_KEY=${LIVEKIT_API_KEY}
LIVEKIT_API_SECRET=${LIVEKIT_API_SECRET}

# Google OAuth (configure later in Settings)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://${DOMAIN}/api/integrations/gmail/callback
ENVEOF
ok ".env written"

# ---- 8. Create data directories ----
mkdir -p "$APP_DIR/backend/data/documents"
mkdir -p "$APP_DIR/backend/data/recordings"

# ---- 9. Run database migrations ----
step "Running database migrations..."
cd "$APP_DIR/backend"
source .venv/bin/activate
alembic upgrade head
ok "Database migrated"

# ---- 10. Build frontend ----
step "Building frontend..."
cd "$APP_DIR/frontend"
# Load nvm in case it's not in PATH
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# Write frontend env (LiveKit URL auto-detected via proxy, but set as fallback)
cat > "$APP_DIR/frontend/.env" <<FEEOF
VITE_LIVEKIT_URL=wss://${DOMAIN}/api/meetings/livekit-proxy
FEEOF

pnpm install --frozen-lockfile
pnpm build
ok "Frontend built → $APP_DIR/frontend/dist"

# ---- 11. Stop any existing instances ----
step "Starting all services..."

# Stop existing backend
if [[ -f "$APP_DIR/backend/uvicorn.pid" ]]; then
    OLD_PID=$(cat "$APP_DIR/backend/uvicorn.pid" 2>/dev/null || echo "")
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
        ok "Stopped previous backend (PID $OLD_PID)"
    fi
fi

# Stop existing LiveKit
if [[ -f "$APP_DIR/livekit.pid" ]]; then
    OLD_PID=$(cat "$APP_DIR/livekit.pid" 2>/dev/null || echo "")
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
        ok "Stopped previous LiveKit (PID $OLD_PID)"
    fi
fi

# Stop existing Hocuspocus
if [[ -f "$APP_DIR/hocuspocus.pid" ]]; then
    OLD_PID=$(cat "$APP_DIR/hocuspocus.pid" 2>/dev/null || echo "")
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
        ok "Stopped previous Hocuspocus (PID $OLD_PID)"
    fi
fi

# ---- 12. Start all services ----

# Start LiveKit server
cd "$APP_DIR"
nohup "$APP_DIR/bin/livekit-server" --config "$APP_DIR/livekit.yaml" \
    > "$APP_DIR/livekit.log" 2>&1 &
echo $! > "$APP_DIR/livekit.pid"
ok "LiveKit started (PID $(cat livekit.pid)) on port 7880"

# Start Hocuspocus collaboration server
cd "$APP_DIR/backend/hocuspocus"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
BACKEND_URL=http://127.0.0.1:8000 HOCUSPOCUS_PORT=1234 \
    nohup node server.js > "$APP_DIR/hocuspocus.log" 2>&1 &
echo $! > "$APP_DIR/hocuspocus.pid"
ok "Hocuspocus started (PID $(cat "$APP_DIR/hocuspocus.pid")) on port 1234"

# Start uvicorn backend
cd "$APP_DIR/backend"
source .venv/bin/activate
nohup "$APP_DIR/backend/.venv/bin/uvicorn" app.main:app \
    --host 0.0.0.0 --port 8000 \
    > "$APP_DIR/backend/uvicorn.log" 2>&1 &
UVICORN_PID=$!
echo "$UVICORN_PID" > "$APP_DIR/backend/uvicorn.pid"
ok "Backend started (PID $UVICORN_PID) on port 8000"

# Give services a moment to start
sleep 3

# Verify backend is running
if curl -sf http://127.0.0.1:8000/api/system/health > /dev/null 2>&1; then
    ok "Backend is responding on port 8000"
else
    warn "Backend may still be starting. Check: tail -f $APP_DIR/backend/uvicorn.log"
fi

# ---- 13. Set up cron jobs for auto-restart on reboot ----
step "Setting up auto-restart cron jobs..."
CRON_BACKEND="@reboot cd $APP_DIR/backend && source .venv/bin/activate && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 & echo \$! > uvicorn.pid"
CRON_LIVEKIT="@reboot cd $APP_DIR && nohup bin/livekit-server --config livekit.yaml > livekit.log 2>&1 & echo \$! > livekit.pid"
CRON_HOCUSPOCUS="@reboot export NVM_DIR=\$HOME/.nvm && [ -s \"\$NVM_DIR/nvm.sh\" ] && source \"\$NVM_DIR/nvm.sh\" && cd $APP_DIR/backend/hocuspocus && BACKEND_URL=http://127.0.0.1:8000 nohup node server.js > $APP_DIR/hocuspocus.log 2>&1 & echo \$! > $APP_DIR/hocuspocus.pid"

# Add cron jobs (remove old entries first)
(crontab -l 2>/dev/null | grep -v "Accountant" || true; echo "$CRON_BACKEND"; echo "$CRON_LIVEKIT"; echo "$CRON_HOCUSPOCUS") | crontab -
ok "Cron jobs installed — all services auto-start on VPS reboot"

# ---- 14. Create helper scripts ----
cat > "$APP_DIR/start.sh" <<'STARTEOF'
#!/usr/bin/env bash
# Start all Accountant services: backend + LiveKit + Hocuspocus
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# Stop existing instances first
"$APP_DIR/stop.sh" 2>/dev/null || true

# Start LiveKit
cd "$APP_DIR"
nohup "$APP_DIR/bin/livekit-server" --config "$APP_DIR/livekit.yaml" \
    > "$APP_DIR/livekit.log" 2>&1 &
echo $! > "$APP_DIR/livekit.pid"
echo "LiveKit started (PID $(cat livekit.pid))"

# Start Hocuspocus
cd "$APP_DIR/backend/hocuspocus"
BACKEND_URL=http://127.0.0.1:8000 HOCUSPOCUS_PORT=1234 \
    nohup node server.js > "$APP_DIR/hocuspocus.log" 2>&1 &
echo $! > "$APP_DIR/hocuspocus.pid"
echo "Hocuspocus started (PID $(cat "$APP_DIR/hocuspocus.pid"))"

# Start backend
cd "$APP_DIR/backend"
source .venv/bin/activate
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
echo $! > uvicorn.pid
echo "Backend started (PID $(cat uvicorn.pid))"

echo "All services running."
STARTEOF
chmod +x "$APP_DIR/start.sh"

cat > "$APP_DIR/stop.sh" <<'STOPEOF'
#!/usr/bin/env bash
# Stop all Accountant services
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

for PIDFILE in "$APP_DIR/backend/uvicorn.pid" "$APP_DIR/livekit.pid" "$APP_DIR/hocuspocus.pid"; do
    SERVICE=$(basename "$PIDFILE" .pid)
    if [[ -f "$PIDFILE" ]]; then
        PID=$(cat "$PIDFILE")
        kill "$PID" 2>/dev/null && echo "Stopped $SERVICE (PID $PID)" || echo "$SERVICE not running"
        rm -f "$PIDFILE"
    else
        echo "$SERVICE: no PID file"
    fi
done
STOPEOF
chmod +x "$APP_DIR/stop.sh"

cat > "$APP_DIR/update.sh" <<'UPDATEEOF'
#!/usr/bin/env bash
# Pull latest code, rebuild, and restart all services
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

echo "Restarting all services..."
"$APP_DIR/stop.sh"
"$APP_DIR/start.sh"

echo "Done! App updated."
UPDATEEOF
chmod +x "$APP_DIR/update.sh"

cat > "$APP_DIR/logs.sh" <<'LOGSEOF'
#!/usr/bin/env bash
# View logs for all services
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE="${1:-all}"

case "$SERVICE" in
    backend) tail -f "$APP_DIR/backend/uvicorn.log" ;;
    livekit) tail -f "$APP_DIR/livekit.log" ;;
    hocuspocus|collab) tail -f "$APP_DIR/hocuspocus.log" ;;
    all|*)
        echo "=== Backend ===" && tail -20 "$APP_DIR/backend/uvicorn.log" 2>/dev/null
        echo ""
        echo "=== LiveKit ===" && tail -20 "$APP_DIR/livekit.log" 2>/dev/null
        echo ""
        echo "=== Hocuspocus ===" && tail -20 "$APP_DIR/hocuspocus.log" 2>/dev/null
        echo ""
        echo "For live logs: $0 backend|livekit|hocuspocus"
        ;;
esac
LOGSEOF
chmod +x "$APP_DIR/logs.sh"

cat > "$APP_DIR/status.sh" <<'STATUSEOF'
#!/usr/bin/env bash
# Check status of all services
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

check_service() {
    local name="$1" pidfile="$2" port="$3"
    if [[ -f "$pidfile" ]]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "\033[0;32m✓ $name running (PID $pid, port $port)\033[0m"
        else
            echo -e "\033[0;31m✗ $name not running (stale PID $pid)\033[0m"
        fi
    else
        echo -e "\033[0;31m✗ $name not running (no PID file)\033[0m"
    fi
}

echo "Service Status:"
echo "───────────────"
check_service "Backend   " "$APP_DIR/backend/uvicorn.pid" "8000"
check_service "LiveKit   " "$APP_DIR/livekit.pid"         "7880"
check_service "Hocuspocus" "$APP_DIR/hocuspocus.pid"      "1234"
STATUSEOF
chmod +x "$APP_DIR/status.sh"

# ---- Done! ----
echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║        Server setup complete!                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Services running:"
echo "    Backend:     http://localhost:8000"
echo "    LiveKit:     http://localhost:7880 (video meetings)"
echo "    Hocuspocus:  http://localhost:1234 (real-time collaboration)"
echo ""
echo -e "${YELLOW}  IMPORTANT — Complete these 2 steps in the DreamHost panel:${NC}"
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
echo "    ~/Accountant/start.sh      # Start all services"
echo "    ~/Accountant/stop.sh       # Stop all services"
echo "    ~/Accountant/status.sh     # Check service status"
echo "    ~/Accountant/update.sh     # Pull + rebuild + restart"
echo "    ~/Accountant/logs.sh       # View recent logs"
echo "    ~/Accountant/logs.sh backend|livekit|hocuspocus  # Live logs"
echo ""
echo -e "${YELLOW}  LiveKit credentials (saved in .env):${NC}"
echo "    API Key:    ${LIVEKIT_API_KEY}"
echo "    API Secret: ${LIVEKIT_API_SECRET}"
echo ""
echo -e "${YELLOW}  Firewall ports needed for video calls:${NC}"
echo "    TCP: 7881 (RTC TCP fallback — required if UDP is blocked)"
echo "    UDP: 50000-50200 (RTC media — ideal, but TCP fallback works)"
echo "    Note: LiveKit signalling goes through the backend proxy (port 8000)"
echo ""
