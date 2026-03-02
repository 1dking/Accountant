# Observability

Monitoring, logging, and alerting configuration for the Accountant platform.

## Existing Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/system/health` | None | Liveness probe — returns `{"data": {"status": "healthy"}}` |
| `GET /api/system/stats` | None | Application metrics (document count, storage used, user count) |

## Files

| File | Purpose |
|------|---------|
| `monitoring.yaml` | Health check intervals, alert thresholds, log levels |
| `logging.py` | Structured JSON logging configuration |

## Log Locations (VPS)

| Service | Log |
|---------|-----|
| Backend (uvicorn) | `~/Accountant/logs/backend.log` |
| LiveKit | `~/Accountant/logs/livekit.log` |
| Hocuspocus | `~/Accountant/logs/hocuspocus.log` |

## Adding Custom Metrics

1. Add metric to `/api/system/stats` endpoint in `backend/app/main.py`
2. Update `monitoring.yaml` with alert thresholds
3. Use structured logging (see `logging.py`) for new log events
