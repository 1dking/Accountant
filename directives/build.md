# Directive: Build Process

## Goal
Set up local development environment or build for production.

## Local Development Setup

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# or: .venv\Scripts\activate     # Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
pnpm install
pnpm dev                         # Starts on port 5173, proxies /api to :8000
```

### Environment
Copy `.env.example` to `backend/.env` and fill in:
- `DATABASE_URL` — leave empty for SQLite default
- `SECRET_KEY` — any random string for local dev
- `ANTHROPIC_API_KEY` — for AI features

## Production Build

### Frontend
```bash
cd frontend
pnpm install --frozen-lockfile
pnpm build                       # Outputs to frontend/dist/
```

Build configuration notes:
- Vite PWA workbox: `maximumFileSizeToCacheInBytes` set to 5MB
- Manual chunks: vendor, tiptap, yjs, livekit, ui
- `VITE_LIVEKIT_URL` baked in at build time (set in frontend `.env` before build)

### Backend
```bash
cd backend
pip install -e .                 # Production dependencies only (no [dev])
alembic upgrade head             # Apply migrations
```

## Verification
- [ ] Backend starts without import errors
- [ ] `GET /api/system/health` returns `{"data": {"status": "healthy"}}`
- [ ] Frontend dev server loads at `http://localhost:5173`
- [ ] Frontend production build completes without TypeScript errors
- [ ] Lint passes: `cd backend && ruff check . && ruff format --check .`

## Edge Cases
- **pnpm not installed**: `npm install -g pnpm`
- **Python < 3.12**: Required for `X | Y` union syntax
- **SQLite for local dev**: No PostgreSQL needed, uses `data/accountant.db`
- **StarterKit history cast**: `StarterKit.configure({ history: false } as any)` required

## Security Requirements
- Never commit `backend/.env`
- Keep `data/` directory gitignored
- Don't install dependencies from untrusted sources
