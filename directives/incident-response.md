# Directive: Incident Response

## Goal
Detect, assess, contain, and recover from production incidents.

## Detection

### Automated
- Health check fails: `curl -sf http://127.0.0.1:8000/api/system/health`
- Service not running: `~/Accountant/status.sh` shows stopped processes
- Error spikes in logs: `~/Accountant/logs.sh` shows repeated errors

### User-Reported
- "Page won't load" → check backend + frontend
- "Can't login" → check auth service + database
- "Payment not working" → check Stripe integration
- "Meetings broken" → check LiveKit + WebSocket proxy

## Assessment

### Step 1: Check Service Status
```bash
~/Accountant/status.sh
```

### Step 2: Check Logs
```bash
~/Accountant/logs.sh
# Or specific service:
tail -100 ~/Accountant/logs/backend.log
```

### Step 3: Check Health Endpoint
```bash
curl -v http://127.0.0.1:8000/api/system/health
```

### Step 4: Check Database
```bash
cd ~/Accountant/backend
source .venv/bin/activate
python -c "from app.database import engine; print('DB OK')"
```

## Common Issues and Fixes

### Backend Won't Start
```bash
# Check for port conflicts
lsof -i :8000
# Check for import errors
cd ~/Accountant/backend && source .venv/bin/activate && python -c "from app.main import app"
# Check for missing dependencies
pip install -e ".[dev]"
# Check for failed migrations
alembic upgrade head
```

### Frontend Shows Blank Page
```bash
# Rebuild frontend
cd ~/Accountant/frontend && pnpm install && pnpm build
# Restart backend (it serves frontend static files)
~/Accountant/stop.sh && ~/Accountant/start.sh
```

### Database Connection Failed
```bash
# Check DATABASE_URL in .env
cat ~/Accountant/backend/.env | grep DATABASE_URL
# Test connection
cd ~/Accountant/backend && source .venv/bin/activate
python -c "import asyncio; from app.database import engine; asyncio.run(engine.dispose())"
```

### TypeScript Build Fails
```bash
# Check the specific error
cd ~/Accountant/frontend && pnpm build 2>&1 | head -50
# Common: unused imports, type errors
# Fix locally, commit, push, then update.sh on VPS
```

### Out of Memory During Build
```bash
# Build frontend locally instead
cd frontend && pnpm build
scp -r frontend/dist/ user@vps:~/Accountant/frontend/dist/
ssh user@vps '~/Accountant/stop.sh && ~/Accountant/start.sh'
```

## Recovery

### Restart All Services
```bash
~/Accountant/stop.sh
~/Accountant/start.sh
```

### Full Redeploy
```bash
~/Accountant/update.sh
```

### Rollback to Previous Version
```bash
cd ~/Accountant
git log --oneline -5              # Find good commit
git revert HEAD                   # Revert latest commit
~/Accountant/update.sh            # Rebuild and restart
```

### Rollback Database Migration
```bash
cd ~/Accountant/backend
source .venv/bin/activate
alembic downgrade -1
~/Accountant/stop.sh && ~/Accountant/start.sh
```

## Post-Incident

1. Document what happened and root cause
2. Update relevant directive with learnings
3. Add monitoring for the failure mode if possible
4. Consider adding a test to prevent recurrence

## Security Considerations
- Never share error logs containing credentials publicly
- If a credential is exposed, rotate it immediately
- Check `.env` file permissions: `chmod 600 ~/Accountant/backend/.env`
- Review access logs if unauthorized access is suspected

## Escalation
- If SSH access is lost: contact DreamHost support
- If domain/DNS issues: check DreamHost panel
- If SSL certificate expired: `certbot renew`
