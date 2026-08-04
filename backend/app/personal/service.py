"""Personal ledger service.

Every query is scoped to ``user_id == user.id`` — personal data is ALWAYS private
to the individual, never org-shared, even inside a shared business org. Amounts +
descriptions are encrypted at rest (the ORM decrypts on attribute access), so
cashflow totals are aggregated in Python rather than SQL — trivial at one-person
scale and mirroring plaid reconciliation_summary.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import NotFoundError
from app.personal.models import PersonalAccount, PersonalCategory, PersonalTransaction

_ZERO = Decimal("0.00")

# Seeded personal-finance categories (kept entirely apart from business ones).
DEFAULT_PERSONAL_CATEGORIES = [
    ("Salary / Income", "in", 1),
    ("Transfer In", "in", 2),
    ("Groceries", "out", 3),
    ("Rent / Mortgage", "out", 4),
    ("Utilities", "out", 5),
    ("Dining / Takeout", "out", 6),
    ("Transport", "out", 7),
    ("Healthcare", "out", 8),
    ("Shopping", "out", 9),
    ("Entertainment", "out", 10),
    ("Transfer Out", "out", 11),
    ("Other", "both", 99),
]


async def seed_personal_categories(db: AsyncSession) -> None:
    """Idempotently seed the default (system) personal categories."""
    existing = (
        await db.execute(
            select(PersonalCategory.name).where(PersonalCategory.is_system.is_(True))
        )
    ).scalars().all()
    have = set(existing)
    added = False
    for name, direction, order in DEFAULT_PERSONAL_CATEGORIES:
        if name not in have:
            db.add(PersonalCategory(
                id=uuid.uuid4(), user_id=None, name=name, direction=direction,
                is_system=True, display_order=order,
            ))
            added = True
    if added:
        await db.commit()


async def list_categories(db: AsyncSession, user: User) -> list[PersonalCategory]:
    """System categories + the user's own, ordered."""
    stmt = select(PersonalCategory).where(
        (PersonalCategory.is_system.is_(True)) | (PersonalCategory.user_id == user.id)
    ).order_by(PersonalCategory.display_order, PersonalCategory.name)
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


async def list_accounts(db: AsyncSession, user: User) -> list[PersonalAccount]:
    stmt = select(PersonalAccount).where(
        PersonalAccount.user_id == user.id,
        PersonalAccount.is_deleted.is_(False),
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_account(db: AsyncSession, user: User, account_id: uuid.UUID) -> PersonalAccount:
    stmt = select(PersonalAccount).where(
        PersonalAccount.id == account_id,
        PersonalAccount.user_id == user.id,
        PersonalAccount.is_deleted.is_(False),
    )
    acct = (await db.execute(stmt)).scalar_one_or_none()
    if acct is None:
        raise NotFoundError("Personal account", str(account_id))
    return acct


async def create_account(db: AsyncSession, user: User, data) -> PersonalAccount:
    acct = PersonalAccount(
        id=uuid.uuid4(), user_id=user.id, name=data.name,
        account_type=data.account_type, currency=data.currency,
        opening_balance=Decimal(str(data.opening_balance or 0)),
        opening_balance_date=data.opening_balance_date, is_active=True,
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return acct


async def update_account(db: AsyncSession, user: User, account_id: uuid.UUID, data) -> PersonalAccount:
    acct = await get_account(db, user, account_id)
    if data.name is not None:
        acct.name = data.name
    if data.account_type is not None:
        acct.account_type = data.account_type
    if data.is_active is not None:
        acct.is_active = data.is_active
    await db.commit()
    await db.refresh(acct)
    return acct


async def delete_account(db: AsyncSession, user: User, account_id: uuid.UUID) -> None:
    acct = await get_account(db, user, account_id)
    acct.is_deleted = True
    await db.commit()


async def account_balance(db: AsyncSession, user: User, account: PersonalAccount) -> Decimal:
    """opening + Σ(in) − Σ(out). Amounts are encrypted → summed in Python."""
    txns = (await db.execute(
        select(PersonalTransaction).where(
            PersonalTransaction.account_id == account.id,
            PersonalTransaction.user_id == user.id,
            PersonalTransaction.is_deleted.is_(False),
        )
    )).scalars().all()
    bal = Decimal(str(account.opening_balance or 0))
    for t in txns:
        amt = Decimal(str(t.amount or 0))
        bal += amt if t.direction == "in" else -amt
    return bal.quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# External ingest (a scanner routes a "personal"-tagged transaction here, in
# addition to its Owner's Draw entry on the business account)
# ---------------------------------------------------------------------------


async def get_or_create_personal_account(
    db: AsyncSession, user: User, external_key: str, label: str
) -> PersonalAccount:
    """One mirror personal account per source (keyed by external_key), so a
    shared bank feed's personal copies all land in the same place."""
    acct = (await db.execute(
        select(PersonalAccount).where(
            PersonalAccount.user_id == user.id,
            PersonalAccount.external_key == external_key,
            PersonalAccount.is_deleted.is_(False),
        )
    )).scalar_one_or_none()
    if acct is not None:
        return acct
    acct = PersonalAccount(
        id=uuid.uuid4(), user_id=user.id, name=label, account_type="bank", currency="CAD",
        opening_balance=Decimal("0.00"), opening_balance_date=date.today(), is_active=True,
        external_key=external_key,
    )
    db.add(acct)
    await db.flush()
    return acct


async def get_personal_by_source(
    db: AsyncSession, user: User, source: str, source_id: str
) -> PersonalTransaction | None:
    return (await db.execute(
        select(PersonalTransaction).where(
            PersonalTransaction.user_id == user.id,
            PersonalTransaction.source == source,
            PersonalTransaction.source_id == source_id,
            PersonalTransaction.is_deleted.is_(False),
        )
    )).scalar_one_or_none()


async def record_personal_from_external(
    db: AsyncSession, user: User, *,
    source: str, source_id: str, txn_date: date, direction: str,
    amount, description: str, personal_category_id, external_key: str, account_label: str,
) -> PersonalTransaction:
    """Idempotently copy a scanner transaction into the Personal ledger. Flushes
    (no commit) so the caller keeps the whole categorize/import atomic."""
    existing = await get_personal_by_source(db, user, source, source_id)
    if existing is not None:
        return existing
    acct = await get_or_create_personal_account(db, user, external_key, account_label)
    txn = PersonalTransaction(
        id=uuid.uuid4(), user_id=user.id, account_id=acct.id, date=txn_date,
        direction=direction, amount=Decimal(str(amount)), description=(description or "")[:500],
        category_id=personal_category_id, source=source, source_id=source_id,
    )
    db.add(txn)
    await db.flush()
    return txn


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


async def list_transactions(
    db: AsyncSession, user: User, *,
    account_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[PersonalTransaction]:
    stmt = select(PersonalTransaction).where(
        PersonalTransaction.user_id == user.id,
        PersonalTransaction.is_deleted.is_(False),
    )
    if account_id:
        stmt = stmt.where(PersonalTransaction.account_id == account_id)
    if date_from:
        stmt = stmt.where(PersonalTransaction.date >= date_from)
    if date_to:
        stmt = stmt.where(PersonalTransaction.date <= date_to)
    stmt = stmt.order_by(PersonalTransaction.date.desc(), PersonalTransaction.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


async def _get_txn(db: AsyncSession, user: User, txn_id: uuid.UUID) -> PersonalTransaction:
    stmt = select(PersonalTransaction).where(
        PersonalTransaction.id == txn_id,
        PersonalTransaction.user_id == user.id,
        PersonalTransaction.is_deleted.is_(False),
    )
    txn = (await db.execute(stmt)).scalar_one_or_none()
    if txn is None:
        raise NotFoundError("Personal transaction", str(txn_id))
    return txn


async def create_transaction(db: AsyncSession, user: User, data) -> PersonalTransaction:
    # Ownership check: the account must be the user's own.
    await get_account(db, user, data.account_id)
    txn = PersonalTransaction(
        id=uuid.uuid4(), user_id=user.id, account_id=data.account_id,
        date=data.date, direction=data.direction,
        amount=Decimal(str(data.amount)), description=data.description,
        category_id=data.category_id, notes=data.notes,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


async def update_transaction(db: AsyncSession, user: User, txn_id: uuid.UUID, data) -> PersonalTransaction:
    txn = await _get_txn(db, user, txn_id)
    if data.date is not None:
        txn.date = data.date
    if data.direction is not None:
        txn.direction = data.direction
    if data.amount is not None:
        txn.amount = Decimal(str(data.amount))
    if data.description is not None:
        txn.description = data.description
    if data.category_id is not None:
        txn.category_id = data.category_id
    if data.notes is not None:
        txn.notes = data.notes
    await db.commit()
    await db.refresh(txn)
    return txn


async def delete_transaction(db: AsyncSession, user: User, txn_id: uuid.UUID) -> None:
    txn = await _get_txn(db, user, txn_id)
    txn.is_deleted = True
    await db.commit()


# ---------------------------------------------------------------------------
# Cashflow summary (Python aggregation over decrypted amounts)
# ---------------------------------------------------------------------------


async def cashflow_summary(
    db: AsyncSession, user: User, *, date_from: date | None = None, date_to: date | None = None,
) -> dict:
    stmt = select(PersonalTransaction).where(
        PersonalTransaction.user_id == user.id,
        PersonalTransaction.is_deleted.is_(False),
    )
    if date_from:
        stmt = stmt.where(PersonalTransaction.date >= date_from)
    if date_to:
        stmt = stmt.where(PersonalTransaction.date <= date_to)
    txns = (await db.execute(stmt)).scalars().all()

    cats = {c.id: c.name for c in await list_categories(db, user)}
    total_in = total_out = _ZERO
    by_cat: dict = {}
    for t in txns:
        amt = Decimal(str(t.amount or 0))
        if t.direction == "in":
            total_in += amt
        else:
            total_out += amt
        key = (t.category_id, t.direction)
        row = by_cat.setdefault(key, {
            "category_id": t.category_id,
            "category_name": cats.get(t.category_id, "Uncategorized"),
            "direction": t.direction, "total": _ZERO, "count": 0,
        })
        row["total"] += amt
        row["count"] += 1

    by_category = sorted(by_cat.values(), key=lambda r: r["total"], reverse=True)
    return {
        "period_start": date_from,
        "period_end": date_to,
        "total_in": total_in.quantize(Decimal("0.01")),
        "total_out": total_out.quantize(Decimal("0.01")),
        "net": (total_in - total_out).quantize(Decimal("0.01")),
        "by_category": by_category,
    }
