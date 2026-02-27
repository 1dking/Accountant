#!/usr/bin/env bash
# ============================================================================
# Accountant — One-Paste VPS Deploy Script
# ============================================================================
# Usage:  SSH into your DreamHost VPS and run:
#   curl -fsSL https://raw.githubusercontent.com/1dking/Accountant/main/deploy.sh | bash
#   -- or --
#   Copy-paste this entire script into your terminal.
#
# Prerequisites: Ubuntu/Debian VPS with sudo access.
# ============================================================================

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

# ---- 1. System packages ----
step "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-venv python3-pip \
    nginx certbot python3-certbot-nginx \
    poppler-utils libmagic1 \
    curl git build-essential

# ---- 2. Install Node.js (LTS) + pnpm ----
step "Installing Node.js LTS..."
if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 20 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
fi
ok "Node.js $(node -v)"

if ! command -v pnpm &>/dev/null; then
    sudo npm install -g pnpm
fi
ok "pnpm $(pnpm -v)"

# ---- 3. Clone repository ----
step "Cloning repository..."
if [[ -d "$APP_DIR" ]]; then
    warn "Directory $APP_DIR already exists — pulling latest..."
    cd "$APP_DIR" && git pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
ok "Repository ready at $APP_DIR"

# ---- 4. Python virtual environment + dependencies ----
step "Setting up Python backend..."
cd "$APP_DIR/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q
ok "Python dependencies installed"

# ---- 5. Generate secrets ----
step "Generating secrets..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ok "SECRET_KEY and FERNET_KEY generated"

# ---- 6. Write .env file ----
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
HOST=127.0.0.1
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

# ---- 7. Create data directory ----
mkdir -p "$APP_DIR/backend/data/documents"

# ---- 8. Run database migrations ----
step "Running database migrations..."
cd "$APP_DIR/backend"
source .venv/bin/activate
alembic upgrade head
ok "Database migrated"

# ---- 9. Build frontend ----
step "Building frontend..."
cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build
ok "Frontend built → $APP_DIR/frontend/dist"

# ---- 10. Install systemd service ----
step "Installing systemd service..."
sed "s|<vps-user>|${VPS_USER}|g" "$APP_DIR/backend/accountant.service" \
    | sudo tee /etc/systemd/system/accountant.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable accountant
sudo systemctl restart accountant
ok "systemd service installed and started"

# Give the backend a moment to start
sleep 2

# Verify backend is running
if curl -sf http://127.0.0.1:8000/api/system/health > /dev/null 2>&1 || \
   curl -sf http://127.0.0.1:8000/docs > /dev/null 2>&1; then
    ok "Backend is responding on port 8000"
else
    warn "Backend may still be starting. Check: sudo journalctl -u accountant -f"
fi

# ---- 11. Install nginx config ----
step "Configuring nginx..."
sed -e "s|<vps-user>|${VPS_USER}|g" \
    -e "s|yourdomain.com|${DOMAIN}|g" \
    "$APP_DIR/backend/nginx.conf.example" \
    | sudo tee /etc/nginx/sites-available/accountant > /dev/null

# Enable site, disable default
sudo ln -sf /etc/nginx/sites-available/accountant /etc/nginx/sites-enabled/accountant
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t && sudo systemctl reload nginx
ok "nginx configured for ${DOMAIN}"

# ---- 12. SSL certificate ----
step "Obtaining SSL certificate..."
echo "Certbot will ask for your email and agreement to terms."
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || {
    warn "Certbot failed. You can run it manually later:"
    warn "  sudo certbot --nginx -d ${DOMAIN}"
}

# ---- Done! ----
echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║           Deployment complete!                   ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  App URL:       https://${DOMAIN}"
echo "  API docs:      https://${DOMAIN}/api/docs"
echo "  Backend logs:  sudo journalctl -u accountant -f"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl restart accountant    # Restart backend"
echo "    sudo systemctl reload nginx          # Reload nginx"
echo "    cd ${APP_DIR} && git pull            # Pull latest code"
echo ""
echo -e "${YELLOW}  Next steps:${NC}"
echo "  1. Open https://${DOMAIN} and register your admin account"
echo "  2. Upload a document to test AI extraction"
echo "  3. Try the mobile receipt capture on your phone"
echo ""

# ---- Update helper script ----
cat > "$APP_DIR/update.sh" <<'UPDATEEOF'
#!/usr/bin/env bash
# Quick update script — pull latest code and rebuild
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Pulling latest code..."
cd "$APP_DIR" && git pull

echo "Updating backend dependencies..."
cd "$APP_DIR/backend"
source .venv/bin/activate
pip install -e ".[dev]" -q

echo "Running migrations..."
alembic upgrade head

echo "Rebuilding frontend..."
cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build

echo "Restarting backend..."
sudo systemctl restart accountant

echo "Done! App updated."
UPDATEEOF
chmod +x "$APP_DIR/update.sh"
ok "Created update.sh for future deployments — just run: ~/Accountant/update.sh"
