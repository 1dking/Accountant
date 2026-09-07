"""Tiny in-process rate limiter for anonymous public endpoints.

Same pattern as auth/router.py's login limiter (fixed window per key,
periodic purge) generalised to (scope, key, limit, window). Good enough
for a single-process deploy; swap the store for Redis if the app ever
runs multiple workers behind one IP-facing edge.
"""
from __future__ import annotations

import time

from fastapi import HTTPException, Request

# bucket → (count, window_start, window_seconds)
_buckets: dict[str, tuple[int, float, float]] = {}
_calls = 0
_PURGE_EVERY = 500


def hit(scope: str, key: str, limit: int, window_seconds: float) -> int | None:
    """Record one hit. Returns None when allowed, or the retry-after
    seconds when the (scope, key) bucket is over `limit` for the window."""
    global _calls  # noqa: PLW0603
    now = time.monotonic()
    _calls += 1
    if _calls >= _PURGE_EVERY:
        _calls = 0
        for k in [k for k, (_, start, win) in _buckets.items() if now - start >= win]:
            _buckets.pop(k, None)
    bucket = f"{scope}:{key}"
    entry = _buckets.get(bucket)
    if entry is None or now - entry[1] >= window_seconds:
        _buckets[bucket] = (1, now, window_seconds)
        return None
    count, start, _ = entry
    if count >= limit:
        return int(window_seconds - (now - start)) + 1
    _buckets[bucket] = (count + 1, start, window_seconds)
    return None


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(request: Request, scope: str, *limits: tuple[int, float]) -> None:
    """Raise 429 (with Retry-After) if any (limit, window) pair is exceeded
    for this client IP. Example: enforce(req, "pages.lead", (10, 60), (50, 86400))."""
    ip = client_ip(request)
    for limit, window in limits:
        retry = hit(f"{scope}:{int(window)}", ip, limit, window)
        if retry is not None:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again shortly.",
                headers={"Retry-After": str(retry)},
            )


def reset() -> None:
    """Test helper."""
    _buckets.clear()
