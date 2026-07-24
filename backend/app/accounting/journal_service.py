"""Manual journal entries — the double-entry posting engine.

A journal entry is a balanced set of debit/credit lines against ChartAccounts,
posted on a date. Rules enforced here:

* every line is exactly one side (debit XOR credit), > 0 — validated in the
  schema, re-checked here defensively;
* the entry balances (Σ debits == Σ credits) and is non-zero;
* every referenced account belongs to the acting tenant and is active;
* the accounting period covering the date is OPEN (posting into a closed period
  is refused — and so is voiding an entry whose date sits in a closed period);
* ``entry_number`` auto-increments per tenant.

Entries are never hard-deleted — a mistake is reversed by VOIDING (keeps the
audit trail), which is itself period-aware.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.accounting.journal_schemas import JournalEntryCreate
from app.accounting.ledger_models import (
    ChartAccount,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)
from app.accounting.period_service import assert_period_open
from app.auth.models import User
from app.core.authorization import apply_cashbook_filter
from app.core.exceptions import NotFoundError, ValidationError


def _org_id_for(user: User) -> uuid.UUID | None:
    if user.cashbook_access == "org" and user.org_id:
        return user.org_id
    return None


async def _next_entry_number(db: AsyncSession, user: User) -> int:
    stmt = select(func.max(JournalEntry.entry_number))
    stmt = apply_cashbook_filter(stmt, JournalEntry.user_id, JournalEntry.org_id, user)
    result = await db.execute(stmt)
    current = result.scalar()
    return (current or 0) + 1


async def _validate_accounts(
    db: AsyncSession, user: User, account_ids: set[uuid.UUID]
) -> None:
    """Every referenced account must belong to the tenant and be active."""
    stmt = select(ChartAccount.id, ChartAccount.is_active).where(
        ChartAccount.id.in_(account_ids)
    )
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    result = await db.execute(stmt)
    found = {row.id: row.is_active for row in result}

    missing = account_ids - set(found)
    if missing:
        # 404-style: don't confirm whether the id exists in another tenant.
        raise NotFoundError("ChartAccount", str(next(iter(missing))))
    inactive = [aid for aid, active in found.items() if not active]
    if inactive:
        raise ValidationError("Cannot post to a deactivated account.")


async def create_entry(
    db: AsyncSession, data: JournalEntryCreate, user: User
) -> JournalEntry:
    await assert_period_open(db, data.date)

    # Defensive re-check of the balance invariant (schema also enforces it).
    debits = sum((ln.debit for ln in data.lines), Decimal("0"))
    credits = sum((ln.credit for ln in data.lines), Decimal("0"))
    if debits != credits or debits == 0:
        raise ValidationError("Journal entry must balance and be non-zero.")

    account_ids = {ln.account_id for ln in data.lines}
    await _validate_accounts(db, user, account_ids)

    entry = JournalEntry(
        user_id=user.id,
        org_id=_org_id_for(user),
        entry_number=await _next_entry_number(db, user),
        date=data.date,
        memo=data.memo,
        source="manual",
        status=JournalEntryStatus.POSTED,
        created_by=user.id,
    )
    for ln in data.lines:
        entry.lines.append(
            JournalLine(
                account_id=ln.account_id,
                debit=ln.debit,
                credit=ln.credit,
                description=ln.description,
            )
        )
    db.add(entry)
    await db.commit()
    return await get_entry(db, entry.id, user)


async def list_entries(
    db: AsyncSession,
    user: User,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    include_void: bool = True,
) -> list[JournalEntry]:
    stmt = select(JournalEntry).options(
        selectinload(JournalEntry.lines).selectinload(JournalLine.entry)
    )
    stmt = apply_cashbook_filter(stmt, JournalEntry.user_id, JournalEntry.org_id, user)
    if date_from is not None:
        stmt = stmt.where(JournalEntry.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.date <= date_to)
    if not include_void:
        stmt = stmt.where(JournalEntry.status == JournalEntryStatus.POSTED)
    stmt = stmt.order_by(JournalEntry.entry_number.desc())
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_entry(
    db: AsyncSession, entry_id: uuid.UUID, user: User
) -> JournalEntry:
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.id == entry_id)
    )
    stmt = apply_cashbook_filter(stmt, JournalEntry.user_id, JournalEntry.org_id, user)
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()
    if entry is None:
        raise NotFoundError("JournalEntry", str(entry_id))
    return entry


async def void_entry(
    db: AsyncSession, entry_id: uuid.UUID, user: User
) -> JournalEntry:
    entry = await get_entry(db, entry_id, user)
    if entry.status == JournalEntryStatus.VOID:
        raise ValidationError("This entry is already void.")
    # Can't disturb a closed period, in either the original or current sense.
    await assert_period_open(db, entry.date)
    entry.status = JournalEntryStatus.VOID
    await db.commit()
    return await get_entry(db, entry_id, user)
