"""Structured logging configuration for the Accountant platform.

Usage:
    from observability.logging import setup_logging
    setup_logging()

Or in FastAPI startup:
    app.add_event_handler("startup", setup_logging)

All logs emitted as JSON with correlation IDs for traceability.
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

# Context variable for request correlation
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if available
        cid = correlation_id.get("")
        if cid:
            log_entry["correlation_id"] = cid

        # Add extra fields if present
        for field in ("user_id", "request_id", "action", "resource_type", "resource_id"):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging for the application.

    Args:
        level: Root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Add JSON handler to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def new_correlation_id() -> str:
    """Generate and set a new correlation ID for the current context."""
    cid = uuid.uuid4().hex[:12]
    correlation_id.set(cid)
    return cid
