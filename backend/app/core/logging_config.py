"""Structured logging + request correlation IDs.

This logic previously lived in `observability/logging.py` at the repo root,
where it was never imported once — and could not have been: the app runs with
`backend/` as the working directory (`uvicorn app.main:app`), so the root-level
`observability` package isn't importable. It was dead code by construction.

JSON output is opt-in via ``json_logs`` so local dev keeps human-readable logs
and any log tooling pointed at the current plain-text format on the VPS doesn't
break the moment this ships. Correlation IDs are always on — they cost nothing
and make a request traceable across every log line it produces.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

#: Set per-request by the correlation middleware; empty outside a request.
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

_EXTRA_FIELDS = ("user_id", "request_id", "action", "resource_type", "resource_id")


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }

        cid = correlation_id.get("")
        if cid:
            entry["correlation_id"] = cid

        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                entry[field] = value

        if record.exc_info and record.exc_info[1]:
            entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(entry, default=str)


class CorrelationIdFilter(logging.Filter):
    """Attach the current correlation ID to plain-text records too, so the
    text format is traceable without forcing everyone onto JSON."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get("") or "-"
        return True


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Configure root logging. Replaces any handlers already attached."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s %(message)s"
            )
        )
        handler.addFilter(CorrelationIdFilter())
    root.addHandler(handler)

    # Quiet noisy libraries to keep signal-to-noise high.
    for noisy in (
        "httpx",
        "httpcore",
        "boto3",
        "botocore",
        "s3transfer",
        "urllib3",
        "uvicorn.access",
        "watchfiles",
        "sqlalchemy.engine",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def new_correlation_id() -> str:
    """Generate and set a correlation ID for the current context."""
    cid = uuid.uuid4().hex[:12]
    correlation_id.set(cid)
    return cid
