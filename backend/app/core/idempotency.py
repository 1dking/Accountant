"""Idempotency-key support for financial POST endpoints.

Clients send an ``Idempotency-Key`` header.  On the first request the endpoint
runs normally and the response is cached.  On subsequent requests with the same
key (per user + endpoint) the cached response is returned immediately, preventing
duplicate financial records.

Usage in a router::

    @router.post("/expenses", status_code=201)
    async def create_expense(
        ...,
        idempotency: IdempotencyResult = Depends(require_idempotency_key),
    ) -> dict:
        if idempotency.cached_response is not None:
            return idempotency.cached_response
        ...  # normal creation logic
        result = {"data": ...}
        await idempotency.save(result, status_code=201)
        return result
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Depends, Header, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.dependencies import get_current_user, get_db


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


@dataclass
class IdempotencyResult:
    """Returned by the dependency.  If ``cached_response`` is not None the
    router should return it directly without executing business logic."""

    cached_response: dict | None = None
    cached_status_code: int | None = None
    _db: AsyncSession = field(repr=False, default=None)  # type: ignore[assignment]
    _key: str = field(repr=False, default="")
    _user_id: uuid.UUID = field(repr=False, default=None)  # type: ignore[assignment]
    _endpoint: str = field(repr=False, default="")

    async def save(self, response_body: dict, status_code: int = 201) -> None:
        """Persist the response so future duplicate requests get the cache."""
        if not self._key:
            return  # no key supplied — nothing to cache
        record = IdempotencyRecord(
            key=self._key,
            user_id=self._user_id,
            endpoint=self._endpoint,
            status_code=status_code,
            response_body=json.dumps(jsonable_encoder(response_body)),
        )
        self._db.add(record)
        await self._db.commit()


async def require_idempotency_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> IdempotencyResult:
    """FastAPI dependency that enforces idempotency on financial POSTs.

    If no ``Idempotency-Key`` header is provided the request proceeds normally
    (backwards-compatible).  If the header IS provided:
      - First time: business logic runs, response cached.
      - Repeat: cached response returned, no side effects.
    """
    endpoint = request.url.path

    if idempotency_key is None:
        return IdempotencyResult(_db=db, _user_id=current_user.id, _endpoint=endpoint)

    # Check for existing record
    result = await db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == idempotency_key,
            IdempotencyRecord.user_id == current_user.id,
            IdempotencyRecord.endpoint == endpoint,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        return IdempotencyResult(
            cached_response=json.loads(existing.response_body),
            cached_status_code=existing.status_code,
            _db=db,
            _key=idempotency_key,
            _user_id=current_user.id,
            _endpoint=endpoint,
        )

    return IdempotencyResult(
        _db=db,
        _key=idempotency_key,
        _user_id=current_user.id,
        _endpoint=endpoint,
    )
