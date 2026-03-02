# Directive: Deployment

## Goal
Deploy or update the Accountant platform on the DreamHost VPS.

## Inputs
- GitHub repository with latest code pushed
- SSH access to VPS
- For fresh deploy: DATABASE_URL, ANTHROPIC_API_KEY, domain name

## Pre-Deployment Checklist
- [ ] All changes committed and pushed to GitHub
- [ ] TypeScript builds locally without errors (`cd frontend && pnpm build`)
- [ ] Backend lint passes (`cd backend && ruff check .`)
- [ ] No `.env` or secrets in the commit
- [ ] Database migrations are included if schema changed

## Fresh Deployment

Run from local machine:
```bash
scp deploy.sh user@vps:~/deploy.sh
ssh user@vps 'bash ~/deploy.sh'
```

The script handles:
1. Clone repository
2. Install Node.js 22 via nvm
3. Install pnpm
4. Create Python venv and install dependencies
5. Download and configure LiveKit server
6. Install Hocuspocus collaboration server
7. Generate secrets (SECRET_KEY, FERNET_KEY)
8. Create `backend/.env` from inputs
9. Run database migrations (`alembic upgrade head`)
10. Build frontend (`pnpm build`)
11. Start all services
12. Verify health check
13. Configure cron for auto-restart on reboot

## Updating (Most Common)

SSH into VPS and run:
```bash
~/Accountant/update.sh
```

This script:
1. `git pull` latest code
2. Install any new Python dependencies
3. Run database migrations
4. Rebuild frontend
5. Restart all services (stop.sh && start.sh)
6. Verify health check

## Post-Deployment Verification
- [ ] `curl http://127.0.0.1:8000/api/system/health` returns healthy
- [ ] Frontend loads in browser at `https://domain.com`
- [ ] Login works
- [ ] Can create/view invoices

## Rollback Procedure

If deployment fails:
```bash
# Stop services
~/Accountant/stop.sh

# Revert to previous commit
cd ~/Accountant && git revert HEAD

# Rebuild and restart
~/Accountant/update.sh
```

If database migration fails:
```bash
cd ~/Accountant/backend
source .venv/bin/activate
alembic downgrade -1
```

## VPS Helper Scripts

| Script | Purpose |
|--------|---------|
| `~/Accountant/start.sh` | Start all services |
| `~/Accountant/stop.sh` | Stop all services |
| `~/Accountant/update.sh` | Pull, rebuild, restart |
| `~/Accountant/logs.sh` | View all service logs |
| `~/Accountant/status.sh` | Check service status |

## Security Requirements

### Threat Model
- SSH key-based authentication only (no password auth)
- `.env` file permissions restricted to owner (`chmod 600`)
- Secrets never committed to git
- HTTPS enforced via certbot/nginx

### Constraints
- DreamHost VPS only proxies port 8000 (FastAPI backend)
- No sudo access — all tools installed in userspace
- LiveKit ports (7880, 50000-50200) may be blocked by firewall
- VPS may have limited memory — frontend build can hang

## Edge Cases
- **Frontend build hangs**: VPS memory too low. Build locally, scp `frontend/dist/` to VPS
- **LiveKit unreachable**: WebSocket proxy through FastAPI at `/api/meetings/livekit-proxy`
- **Migration fails**: Check if using SQLite-specific syntax. All migrations must use `render_as_batch=True`
- **Port 8000 already in use**: `~/Accountant/stop.sh` first, then check with `lsof -i :8000`

## Evaluation Criteria
- Health check returns 200
- Frontend loads without errors
- All services running (`status.sh`)
- No error spikes in logs after deploy
