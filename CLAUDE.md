# Accountant

## Project Overview
Full-stack document vault & accounting suite. FastAPI backend + React frontend.
Local (SQLite) or deployed (PostgreSQL).

## Tech Stack
- Backend: Python 3.12+ / FastAPI / SQLAlchemy 2.0 async / Alembic / Pydantic v2
- Frontend: React 19 / TypeScript / Vite / TailwindCSS v4 / shadcn/ui / Zustand / TanStack Query
- Database: SQLite (local) / PostgreSQL (deployed) -- controlled by DATABASE_URL env var
- Real-time: FastAPI WebSockets
- AI: Anthropic Claude API (Vision + tool use)
- Auth: JWT (python-jose) + bcrypt (passlib)

## Project Structure
- `backend/app/` -- FastAPI application (modular: auth/, documents/, collaboration/, notifications/, calendar/, ai/, accounting/)
- `backend/alembic/` -- database migrations
- `backend/tests/` -- pytest test suite
- `frontend/src/` -- React app (api/, components/, pages/, stores/, hooks/, types/)
- `data/` -- runtime data directory (gitignored): SQLite DB + uploaded documents

## Development Commands
- Backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && pnpm dev` (port 5173, proxies /api to :8000)
- Tests: `cd backend && pytest -v`
- Migrations: `cd backend && alembic upgrade head`
- New migration: `cd backend && alembic revision --autogenerate -m "description"`
- Frontend build: `cd frontend && pnpm build`
- Lint: `cd backend && ruff check . && ruff format --check .`

## Code Conventions
- Backend: snake_case everywhere. Type hints required. Async functions for all DB/IO operations.
- Frontend: camelCase for variables/functions, PascalCase for components. Props interfaces named `{Component}Props`.
- API responses use envelope format: `{ data, meta }` for success, `{ error: { code, message } }` for errors.
- Every backend module follows: `models.py` (SQLAlchemy), `schemas.py` (Pydantic), `service.py` (business logic), `router.py` (endpoints).
- Database models use SQLAlchemy 2.0 `Mapped[]` syntax with `mapped_column()`.
- Frontend API calls go through `src/api/client.ts` (never raw fetch in components).
- State: server state in TanStack Query, client state in Zustand.
- Components use shadcn/ui primitives. Custom components go in `components/{domain}/`.

## Architecture Rules
- Storage is abstracted via `StorageBackend` protocol -- never access filesystem directly in services.
- Auth dependencies: `get_current_user` for any authenticated route, `require_role([...])` for role-restricted routes.
- All significant actions must be logged to ActivityLog (for the activity feed).
- Notifications are created server-side and pushed via WebSocket.
- Database-agnostic: never use SQLite-specific or PostgreSQL-specific SQL. Always go through SQLAlchemy ORM.
- Alembic migrations must use `render_as_batch=True` for SQLite compatibility.

## Testing
- Use pytest + pytest-asyncio for backend tests.
- Test fixtures in `backend/tests/conftest.py`: test DB (in-memory SQLite), test client, authenticated user helpers.
- Every new endpoint needs at least: happy path test, auth test (unauthenticated returns 401), role test (wrong role returns 403).

## Do NOT
- Commit `.env`, `data/`, or any file containing secrets.
- Use synchronous database calls.
- Put business logic in routers -- routers only validate input and call services.
- Use `select *` or load full document file contents into memory for listing endpoints.

---

## Agent Architecture

This project follows a multi-layer agent architecture for structured, repeatable operations.

### Layers

| Layer | Purpose | Location |
|-------|---------|----------|
| **Directive** | SOPs defining what to do, inputs, outputs, edge cases, security | `directives/` |
| **Orchestration** | Intelligent routing, decision-making, error handling | Claude Code (this agent) |
| **Execution** | Deterministic scripts for deployment, builds, maintenance | `execution/`, `deploy.sh` |
| **Observability** | Monitoring, logging, alerting, audit trails | `observability/` |
| **Evaluation** | Test suites, quality gates, benchmarks | `evaluation/` |
| **Security** | Policies, access controls, input validation patterns | `security/` |

### Operating Principles

1. **Security-first**: Every directive includes threat model and security requirements. All inputs validated, outputs verified.
2. **Observability by default**: Structured logging, correlation IDs, health checks, audit trails.
3. **Check for tools first**: Before writing a script, check `execution/` per the directive. Only create new scripts if none exist.
4. **Self-anneal when things break**: Read error → fix → test → update directive with learnings.
5. **Update directives as you learn**: Directives are living documents. Update with API constraints, edge cases, timing, security findings.
6. **Continuous evaluation**: Run tests before/after changes. Measure accuracy, safety, performance, cost.

### Framework Directory Structure

```
directives/           # SOPs: deployment, build, API endpoint, migration, incident response
execution/            # Deterministic scripts (references deploy.sh)
.tmp/                 # Temporary processing files (gitignored)
observability/        # Monitoring configs, structured logging
evaluation/           # Test suites, quality gates, benchmarks
security/             # Policies, access control reference, validation patterns
config/               # System configuration (agent.yaml)
logs/                 # Runtime logs (gitignored)
```

### Key Directives

| Directive | When to use |
|-----------|-------------|
| `directives/deployment.md` | Deploying to VPS, running update.sh |
| `directives/build.md` | Setting up dev environment, building frontend |
| `directives/api-endpoint.md` | Creating a new backend module/endpoint |
| `directives/database-migration.md` | Adding/changing database models |
| `directives/incident-response.md` | When something breaks in production |
