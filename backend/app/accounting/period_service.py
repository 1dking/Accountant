"""Business logic for accounting period closing/locking."""


import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.period_models import AccountingPeriod, PeriodStatus
from app.auth.models import User
from app.core.exceptions import ConflictError, NotFoundError, ValidationError


async def list_periods(db: AsyncSession) -> list[AccountingPeriod]:
    """Return all accounting periods, ordered by year/month descending."""
    result = await db.execute(
        select(AccountingPeriod).order_by(
            AccountingPeriod.year.desc(),
            AccountingPeriod.month.desc(),
        )
    )
    return list(result.scalars().all())


async def close_period(
    db: AsyncSession,
    year: int,
    month: int,
    user: User,
    notes: str | None = None,
) -> AccountingPeriod:
    """Close (lock) an accounting period. Creates the period row if needed."""
    result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.year == year,
            AccountingPeriod.month == month,
        )
    )
    period = result.scalar_one_or_none()

    if period is not None and period.status == PeriodStatus.CLOSED:
        raise ConflictError(
            f"The period {year}-{month:02d} is already closed."
        )

    if period is None:
        period = AccountingPeriod(
            year=year,
            month=month,
            status=PeriodStatus.CLOSED,
            closed_by=user.id,
            closed_at=datetime.now(timezone.utc),
            notes=notes,
        )
        db.add(period)
    else:
        period.status = PeriodStatus.CLOSED
        period.closed_by = user.id
        period.closed_at = datetime.now(timezone.utc)
        period.notes = notes

    await db.commit()
    await db.refresh(period)
    return period


async def reopen_period(
    db: AsyncSession,
    period_id: uuid.UUID,
    user: User,
    notes: str | None = None,
) -> AccountingPeriod:
    """Reopen a previously closed accounting period."""
    result = await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id)
    )
    period = result.scalar_one_or_none()
    if period is None:
        raise NotFoundError("AccountingPeriod", str(period_id))

    if period.status == PeriodStatus.OPEN:
        raise ValidationError(
            f"The period {period.year}-{period.month:02d} is already open."
        )

    period.status = PeriodStatus.OPEN
    period.closed_by = None
    period.closed_at = None
    period.notes = notes

    await db.commit()
    await db.refresh(period)
    return period


async def is_period_open(db: AsyncSession, target_date: date) -> bool:
    """Check whether the accounting period for a given date is open.

    Returns True if the period is open (or if no period row exists yet).
    Returns False if the period is explicitly closed.
    """
    result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.year == target_date.year,
            AccountingPeriod.month == target_date.month,
        )
    )
    period = result.scalar_one_or_none()
    if period is None:
        return True  # No period row means it's open by default
    return period.status == PeriodStatus.OPEN


async def assert_period_open(db: AsyncSession, target_date: date) -> None:
    """Raise ValidationError if the period containing *target_date* is closed."""
    if not await is_period_open(db, target_date):
        raise ValidationError(
            f"The accounting period {target_date.year}-{target_date.month:02d} "
            f"is closed. No changes are allowed in a closed period."
        )
