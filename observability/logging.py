"""MOVED — this module is not importable by the app and is no longer the source of truth.

The application runs with `backend/` as its working directory
(`uvicorn app.main:app`), so a root-level `observability` package can never be
imported from it. This file sat here unreferenced: a working JSON formatter and
correlation-ID contextvar that nothing could load.

The implementation now lives where it can actually run, and IS wired into the
FastAPI app at startup:

    backend/app/core/logging_config.py

    from app.core.logging_config import setup_logging, correlation_id

JSON output is opt-in via the JSON_LOGS env var; correlation IDs are always on
and are echoed to clients as the X-Request-ID response header.
"""
