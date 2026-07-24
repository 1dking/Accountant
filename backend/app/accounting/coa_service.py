"""Chart of Accounts — seeding, migration of flat categories, and CRUD.

The Chart of Accounts is the spine of Phase 1 (Trustable books). Every posting
references a ChartAccount. The service does three jobs:

1. **Seed** a standard numbered CoA per tenant (idempotent).
2. **Migrate** the existing flat cashbook onto it — each tenant PaymentAccount
   gets a CoA asset account, and the income/expense categories get CoA
   income/expense accounts.
3. **CRUD** the tenant's own accounts, always scoped through
   ``apply_cashbook_filter`` so one tenant can never see or mutate another's.

A note on tenancy and categories
--------------------------------
``PaymentAccount`` is tenant-scoped (user_id/org_id), so ``coa_account_id`` on it
is unambiguous. ``TransactionCategory`` is a legacy GLOBAL table (name unique
install-wide, no owner column), so its ``coa_account_id`` is only set for a
category this tenant actually owns (``created_by == user.id``) — never for a
shared/system category, which would leak one tenant's CoA account into another
tenant's report. The General Ledger (P1.3) therefore resolves a cashbook entry's
category to the *acting tenant's* CoA account by name/type at report time, and
treats ``category.coa_account_id`` as a cache only. Seeding still creates the
per-tenant CoA income/expense accounts so that name-based resolution always finds
a home.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.coa_schemas import (
    ChartAccountCreate,
    ChartAccountUpdate,
    CoASeedResult,
)
from app.accounting.ledger_models import AccountType, ChartAccount
from app.auth.models import User
from app.cashbook.models import CategoryType, PaymentAccount, TransactionCategory
from app.core.authorization import apply_cashbook_filter, is_admin
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The standard seeded chart. is_system accounts survive tenant customisation.
# ---------------------------------------------------------------------------

#: (code, name, type). Ordered by code. Gaps are intentional so a tenant can
#: insert their own accounts between the seeded ones.
DEFAULT_COA: list[tuple[str, str, AccountType]] = [
    # Assets 1000-1999
    ("1000", "Cash on Hand", AccountType.ASSET),
    ("1010", "Business Checking", AccountType.ASSET),
    ("1200", "Accounts Receivable", AccountType.ASSET),
    ("1500", "Undeposited Funds", AccountType.ASSET),
    # Liabilities 2000-2999
    ("2000", "Accounts Payable", AccountType.LIABILITY),
    ("2100", "Sales Tax Payable", AccountType.LIABILITY),
    ("2200", "Credit Card Payable", AccountType.LIABILITY),
    # Equity 3000-3999
    ("3000", "Owner's Equity", AccountType.EQUITY),
    ("3900", "Retained Earnings", AccountType.EQUITY),
    # Income 4000-4999
    ("4000", "Sales Revenue", AccountType.INCOME),
    ("4100", "Service Revenue", AccountType.INCOME),
    ("4900", "Other Income", AccountType.INCOME),
    # Expenses 5000-6999
    ("5000", "Cost of Goods Sold", AccountType.EXPENSE),
    ("6000", "Advertising & Marketing", AccountType.EXPENSE),
    ("6100", "Bank & Merchant Fees", AccountType.EXPENSE),
    ("6200", "Meals & Entertainment", AccountType.EXPENSE),
    ("6300", "Office Supplies", AccountType.EXPENSE),
    ("6400", "Rent", AccountType.EXPENSE),
    ("6500", "Travel", AccountType.EXPENSE),
    ("6600", "Utilities", AccountType.EXPENSE),
    ("6900", "Other Expenses", AccountType.EXPENSE),
]

#: Well-known accounts the posting engine (P1.2-P1.4) looks up by code.
CODE_ACCOUNTS_PAYABLE = "2000"
CODE_UNDEPOSITED = "1500"
CODE_OTHER_INCOME = "4900"
CODE_OTHER_EXPENSE = "6900"

#: Where migrated categories/payment-accounts land when we auto-number them.
_INCOME_BASE = 4000
_EXPENSE_BASE = 6000
_ASSET_BASE = 1010


def _org_id_for(user: User) -> uuid.UUID | None:
    """The org_id a new tenant-scoped row should carry, mirroring the cashbook."""
    if user.cashbook_access == "org" and user.org_id:
        return user.org_id
    return None


async def _tenant_accounts(db: AsyncSession, user: User) -> list[ChartAccount]:
    stmt = select(ChartAccount)
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    result = await db.execute(stmt.order_by(ChartAccount.code))
    return list(result.scalars().all())


async def _used_codes(db: AsyncSession, user: User) -> set[str]:
    return {a.code for a in await _tenant_accounts(db, user)}


def _next_code(base: int, used: set[str]) -> str:
    """First free code at or after *base* (increments by 10)."""
    n = base
    while str(n) in used:
        n += 10
    used.add(str(n))
    return str(n)


# ---------------------------------------------------------------------------
# Seed + migrate
# ---------------------------------------------------------------------------


async def seed_default_coa(
    db: AsyncSession,
    user: User,
    *,
    migrate: bool = True,
    commit: bool = True,
) -> CoASeedResult:
    """Idempotently seed the standard CoA for this tenant and (optionally)
    migrate the flat cashbook onto it.

    Safe to call repeatedly: existing accounts are never duplicated (matched by
    code within the tenant), and already-mapped categories/payment-accounts are
    left alone.
    """
    org_id = _org_id_for(user)
    existing = {a.code: a for a in await _tenant_accounts(db, user)}
    already_seeded = any(a.is_system for a in existing.values())

    created = 0
    for code, name, acct_type in DEFAULT_COA:
        if code in existing:
            continue
        acct = ChartAccount(
            user_id=user.id,
            org_id=org_id,
            code=code,
            name=name,
            account_type=acct_type,
            is_system=True,
        )
        db.add(acct)
        existing[code] = acct
        created += 1

    categories_mapped = 0
    payment_accounts_mapped = 0
    if migrate:
        # Flush so the seeded accounts have identities for FK references.
        await db.flush()
        categories_mapped = await _migrate_categories(db, user, existing)
        payment_accounts_mapped = await _migrate_payment_accounts(db, user, existing)

    if commit:
        await db.commit()

    return CoASeedResult(
        accounts_created=created,
        categories_mapped=categories_mapped,
        payment_accounts_mapped=payment_accounts_mapped,
        already_seeded=already_seeded,
    )


async def _migrate_payment_accounts(
    db: AsyncSession,
    user: User,
    coa_by_code: dict[str, ChartAccount],
) -> int:
    """Give each tenant PaymentAccount a CoA asset account (creating one if the
    account name doesn't already map). Only touches accounts with no mapping."""
    org_id = _org_id_for(user)
    stmt = select(PaymentAccount)
    stmt = apply_cashbook_filter(stmt, PaymentAccount.user_id, PaymentAccount.org_id, user)
    result = await db.execute(stmt)
    accounts = list(result.scalars().all())

    used = set(coa_by_code.keys())
    by_name = {a.name.strip().lower(): a for a in coa_by_code.values()}
    mapped = 0
    for pa in accounts:
        if pa.coa_account_id is not None:
            continue
        key = pa.name.strip().lower()
        coa = by_name.get(key)
        if coa is None:
            code = _next_code(_ASSET_BASE, used)
            coa = ChartAccount(
                user_id=user.id,
                org_id=org_id,
                code=code,
                name=pa.name[:120],
                account_type=AccountType.ASSET,
            )
            db.add(coa)
            await db.flush()
            coa_by_code[code] = coa
            by_name[key] = coa
        pa.coa_account_id = coa.id
        mapped += 1
    return mapped


async def _migrate_categories(
    db: AsyncSession,
    user: User,
    coa_by_code: dict[str, ChartAccount],
) -> int:
    """Ensure a per-tenant CoA income/expense account exists for every category,
    so report-time name resolution always lands. Sets ``category.coa_account_id``
    ONLY for categories this tenant owns (see module docstring on why globals are
    left untouched)."""
    org_id = _org_id_for(user)
    result = await db.execute(select(TransactionCategory))
    categories = list(result.scalars().all())

    used = set(coa_by_code.keys())
    by_name = {a.name.strip().lower(): a for a in coa_by_code.values()}
    mapped = 0
    for cat in categories:
        # BOTH-typed categories can't map to a single normal-balance account;
        # the report splits them by the entry's own income/expense type.
        if cat.category_type == CategoryType.INCOME:
            base, acct_type = _INCOME_BASE, AccountType.INCOME
        elif cat.category_type == CategoryType.EXPENSE:
            base, acct_type = _EXPENSE_BASE, AccountType.EXPENSE
        else:
            continue

        key = cat.name.strip().lower()
        coa = by_name.get(key)
        if coa is None or coa.account_type != acct_type:
            code = _next_code(base, used)
            coa = ChartAccount(
                user_id=user.id,
                org_id=org_id,
                code=code,
                name=cat.name[:120],
                account_type=acct_type,
            )
            db.add(coa)
            await db.flush()
            coa_by_code[code] = coa
            by_name[key] = coa

        # Only cache the pointer on a category this tenant owns. A shared/system
        # category is resolved by name per-tenant at report time instead.
        owns = cat.created_by == user.id or is_admin(user)
        if owns and cat.coa_account_id is None:
            cat.coa_account_id = coa.id
            mapped += 1
    return mapped


# ---------------------------------------------------------------------------
# CRUD (tenant-scoped)
# ---------------------------------------------------------------------------


async def list_accounts(
    db: AsyncSession,
    user: User,
    *,
    account_type: AccountType | None = None,
    include_inactive: bool = False,
) -> list[ChartAccount]:
    stmt = select(ChartAccount)
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    if account_type is not None:
        stmt = stmt.where(ChartAccount.account_type == account_type)
    if not include_inactive:
        stmt = stmt.where(ChartAccount.is_active.is_(True))
    result = await db.execute(stmt.order_by(ChartAccount.code))
    return list(result.scalars().all())


async def get_account(
    db: AsyncSession, account_id: uuid.UUID, user: User
) -> ChartAccount:
    stmt = select(ChartAccount).where(ChartAccount.id == account_id)
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account is None:
        raise NotFoundError("ChartAccount", str(account_id))
    return account


async def _code_in_use(
    db: AsyncSession, user: User, code: str, *, exclude_id: uuid.UUID | None = None
) -> bool:
    stmt = select(ChartAccount.id).where(ChartAccount.code == code)
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    if exclude_id is not None:
        stmt = stmt.where(ChartAccount.id != exclude_id)
    result = await db.execute(stmt)
    return result.first() is not None


async def _validate_parent(
    db: AsyncSession, user: User, parent_id: uuid.UUID, *, self_id: uuid.UUID | None = None
) -> ChartAccount:
    if self_id is not None and parent_id == self_id:
        raise ValidationError("An account cannot be its own parent.")
    parent = await get_account(db, parent_id, user)  # tenant-scoped; 404 if foreign
    return parent


async def create_account(
    db: AsyncSession, data: ChartAccountCreate, user: User
) -> ChartAccount:
    if await _code_in_use(db, user, data.code):
        raise ConflictError(f"Account code {data.code} already exists.")
    if data.parent_id is not None:
        await _validate_parent(db, user, data.parent_id)

    account = ChartAccount(
        user_id=user.id,
        org_id=_org_id_for(user),
        code=data.code,
        name=data.name,
        account_type=data.account_type,
        description=data.description,
        parent_id=data.parent_id,
        is_active=data.is_active,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def update_account(
    db: AsyncSession, account_id: uuid.UUID, data: ChartAccountUpdate, user: User
) -> ChartAccount:
    account = await get_account(db, account_id, user)

    if data.code is not None and data.code != account.code:
        if account.is_system:
            raise ForbiddenError("The code of a system account cannot be changed.")
        if await _code_in_use(db, user, data.code, exclude_id=account.id):
            raise ConflictError(f"Account code {data.code} already exists.")
        account.code = data.code

    if data.name is not None:
        account.name = data.name
    if data.description is not None:
        account.description = data.description
    if data.parent_id is not None:
        await _validate_parent(db, user, data.parent_id, self_id=account.id)
        account.parent_id = data.parent_id
    if data.is_active is not None:
        account.is_active = data.is_active

    await db.commit()
    await db.refresh(account)
    return account


async def deactivate_account(
    db: AsyncSession, account_id: uuid.UUID, user: User
) -> ChartAccount:
    """Soft-delete: accounts are never hard-deleted because postings reference
    them. A system account can be deactivated but not removed."""
    account = await get_account(db, account_id, user)
    account.is_active = False
    await db.commit()
    await db.refresh(account)
    return account


# Late import to avoid a cycle at module load; ForbiddenError is only used in
# update_account's system-code guard.
from app.core.exceptions import ForbiddenError  # noqa: E402
