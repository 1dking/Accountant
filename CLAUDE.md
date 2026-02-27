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
