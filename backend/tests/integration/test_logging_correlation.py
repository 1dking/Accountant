"""Structured logging + correlation IDs.

`observability/logging.py` was a complete, working structured logger that was
never imported once — and couldn't be: the app runs from `backend/`, so a
root-level `observability` package isn't on the path. It was dead by
construction. The implementation now lives in `app/core/logging_config.py` and
is wired into the app at startup.
"""
import json
import logging

import pytest

from app.core.logging_config import (
    JSONFormatter,
    correlation_id,
    new_correlation_id,
    setup_logging,
)


@pytest.mark.high
async def test_response_carries_a_correlation_id(client):
    resp = await client.get("/api/system/health")
    assert "X-Request-ID" in resp.headers
    assert resp.headers["X-Request-ID"]


@pytest.mark.high
async def test_inbound_request_id_is_preserved(client):
    """A proxy or caller-supplied id must survive, so a trace spans the hop."""
    resp = await client.get(
        "/api/system/health", headers={"X-Request-ID": "trace-abc-123"}
    )
    assert resp.headers["X-Request-ID"] == "trace-abc-123"


@pytest.mark.high
async def test_each_request_gets_a_distinct_id(client):
    first = await client.get("/api/system/health")
    second = await client.get("/api/system/health")
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


@pytest.mark.high
def test_json_formatter_emits_parseable_json_with_correlation_id():
    new_correlation_id()
    cid = correlation_id.get("")

    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    payload = json.loads(JSONFormatter().format(record))

    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["module"] == "app.test"
    assert payload["correlation_id"] == cid


@pytest.mark.high
def test_json_formatter_captures_exceptions():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JSONFormatter().format(record))
    assert payload["exception"]["type"] == "ValueError"
    assert payload["exception"]["message"] == "boom"


@pytest.mark.high
def test_setup_logging_is_idempotent():
    """It's called at import time; a second call must not stack handlers."""
    setup_logging()
    first = len(logging.getLogger().handlers)
    setup_logging()
    assert len(logging.getLogger().handlers) == first
