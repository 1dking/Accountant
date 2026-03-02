# Config

System configuration templates for the Accountant platform.

## Files

| File | Purpose |
|------|---------|
| `agent.yaml` | Project metadata, environment settings, service ports, feature flags |

## Environment Configuration

Runtime configuration is handled via environment variables in `backend/.env`.
See `.env.example` at project root for available settings.

Key configuration areas:
- `DATABASE_URL` — SQLite (local) or PostgreSQL (production)
- `SECRET_KEY` — JWT signing key
- `FERNET_KEY` — Encryption key for sensitive data
- `ANTHROPIC_API_KEY` — Claude AI integration
- `STRIPE_*` — Payment processing
- `LIVEKIT_*` — Video meeting infrastructure
