# Accountant — Project Override

Project: Accountant (OSM Accounting Module)
Repo: github.com/[org]/Accountant
Stack: React/TypeScript + Python/FastAPI + PostgreSQL (Supabase)
Deploy: accountant.ocidm.io (DreamHost VPS, port 8000)
Owner: Nate (nathano@ocidm.com) — OCIDM

## Global Framework
See `~/.claude/` for architecture, conventions, security, tools, protocols, learnings.

## Project-Specific Rules
- Build tool: **pnpm** (not npm)
- VPS deploy: `ssh dh_pjj4dt@vps18033.dreamhostps.com 'cd ~/Accountant && bash deploy.sh'`
- Frontend served by backend via FastAPI StaticFiles (no separate web server)
- SQLAlchemy async sessions with `expire_on_commit=False`
- After long async ops (AI calls), always rollback + re-fetch before writes
- Multi-tenant: `apply_cashbook_filter()` scopes all queries by org/user

## Active Sprint
See `.claude/active-sprint.md` for current session priorities.
