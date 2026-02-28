"""Business logic for the cashbook module."""

import logging
import time
import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.cashbook.models import (
    AccountType,
    CashbookEntry,
    CategoryType,
    EntryType,
    PaymentAccount,
    TransactionCategory,
)
from app.cashbook.schemas import (
    CashbookEntryCreate,
    CashbookEntryFilter,
    CashbookEntryUpdate,
    CategoryTotal,
    PaymentAccountCreate,
    PaymentAccountUpdate,
)
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta

if TYPE_CHECKING:
    from app.documents.models import Document
    from app.documents.storage import StorageBackend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default transaction categories (matching the accountant's spreadsheet)
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES = [
    # Income categories
    {"name": "Grant", "category_type": "income", "color": "#22c55e", "icon": "gift", "order": 1},
    {"name": "HST/GST Collected", "category_type": "income", "color": "#16a34a", "icon": "receipt", "order": 2},
    {"name": "Fees", "category_type": "income", "color": "#15803d", "icon": "dollar-sign", "order": 3},
    {"name": "Rental Income", "category_type": "income", "color": "#14532d", "icon": "home", "order": 4},
    {"name": "Other Income", "category_type": "income", "color": "#4ade80", "icon": "circle-plus", "order": 5},
    # Expense categories
    {"name": "HST/GST Paid", "category_type": "expense", "color": "#ef4444", "icon": "receipt", "order": 6},
    {"name": "Advertising", "category_type": "expense", "color": "#f97316", "icon": "megaphone", "order": 7},
    {"name": "Inventory", "category_type": "expense", "color": "#eab308", "icon": "package", "order": 8},
    {"name": "Shipping", "category_type": "expense", "color": "#84cc16", "icon": "truck", "order": 9},
    {"name": "Fuel", "category_type": "expense", "color": "#f59e0b", "icon": "fuel", "order": 10},
    {"name": "Credit Card Payment", "category_type": "expense", "color": "#6366f1", "icon": "credit-card", "order": 11},
    {"name": "Meals", "category_type": "expense", "color": "#ec4899", "icon": "utensils", "order": 12},
    {"name": "Depreciation", "category_type": "expense", "color": "#78716c", "icon": "trending-down", "order": 13},
    {"name": "Dues & Subscriptions", "category_type": "expense", "color": "#8b5cf6", "icon": "monitor", "order": 14},
    {"name": "Education & Training", "category_type": "expense", "color": "#0ea5e9", "icon": "graduation-cap", "order": 15},
    {"name": "Insurance General", "category_type": "expense", "color": "#3b82f6", "icon": "shield", "order": 16},
    {"name": "Insurance Vehicles", "category_type": "expense", "color": "#2563eb", "icon": "car", "order": 17},
    {"name": "Interest Expense", "category_type": "expense", "color": "#7c3aed", "icon": "percent", "order": 18},
    {"name": "Meals & Entertainment", "category_type": "expense", "color": "#db2777", "icon": "wine", "order": 19},
    {"name": "Office Supplies", "category_type": "expense", "color": "#d97706", "icon": "paperclip", "order": 20},
    {"name": "Professional Fees", "category_type": "expense", "color": "#4f46e5", "icon": "briefcase", "order": 21},
    {"name": "Rent", "category_type": "expense", "color": "#059669", "icon": "building", "order": 22},
    {"name": "Repairs & Maintenance", "category_type": "expense", "color": "#0891b2", "icon": "wrench", "order": 23},
    {"name": "Corporate Tax", "category_type": "expense", "color": "#64748b", "icon": "landmark", "order": 24},
    {"name": "Telephone Land", "category_type": "expense", "color": "#0d9488", "icon": "phone", "order": 25},
    {"name": "Telephone Wireless", "category_type": "expense", "color": "#14b8a6", "icon": "smartphone", "order": 26},
    {"name": "Travel", "category_type": "expense", "color": "#06b6d4", "icon": "plane", "order": 27},
    {"name": "Utilities", "category_type": "expense", "color": "#a855f7", "icon": "zap", "order": 28},
    {"name": "Vehicle Fuel", "category_type": "expense", "color": "#e11d48", "icon": "fuel", "order": 29},
    {"name": "Vehicle Repairs", "category_type": "expense", "color": "#be123c", "icon": "car", "order": 30},
    {"name": "Other Expense", "category_type": "expense", "color": "#6b7280", "icon": "circle-dot", "order": 31},
]


# ---------------------------------------------------------------------------
# Tax calculation
# ---------------------------------------------------------------------------


def calculate_tax(total_amount: float, tax_rate: float) -> float:
    """Extract tax from a tax-inclusive amount.

    For Ontario HST at 13%: tax = total - (total / 1.13)
    This matches the spreadsheet formula: =amount/1.13
    """
    if tax_rate <= 0:
        return 0.0
    tax_multiplier = 1 + (tax_rate / 100)
    pre_tax = total_amount / tax_multiplier
    return round(total_amount - pre_tax, 2)


# ---------------------------------------------------------------------------
# Category seeding
# ---------------------------------------------------------------------------


async def seed_default_categories(db: AsyncSession) -> list[TransactionCategory]:
    """Create built-in transaction categories if they don't exist yet."""
    result = await db.execute(
        select(TransactionCategory).where(TransactionCategory.is_system.is_(True))
    )
    existing = {cat.name for cat in result.scalars().all()}

    created = []
    for cat_data in DEFAULT_CATEGORIES:
        if cat_data["name"] not in existing:
            cat = TransactionCategory(
                name=cat_data["name"],
                category_type=CategoryType(cat_data["category_type"]),
                color=cat_data["color"],
                icon=cat_data["icon"],
                is_system=True,
                display_order=cat_data["order"],
            )
            db.add(cat)
            created.append(cat)

    if created:
        await db.commit()
        for cat in created:
            await db.refresh(cat)

    return created


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


async def list_categories(
    db: AsyncSession,
    category_type: CategoryType | None = None,
) -> list[TransactionCategory]:
    query = select(TransactionCategory).order_by(TransactionCategory.display_order)
    if category_type is not None:
        query = query.where(
            or_(
                TransactionCategory.category_type == category_type,
                TransactionCategory.category_type == CategoryType.BOTH,
            )
        )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_category(
    db: AsyncSession,
    name: str,
    category_type: CategoryType,
    user: User,
    color: str | None = None,
    icon: str | None = None,
) -> TransactionCategory:
    result = await db.execute(
        select(TransactionCategory).where(TransactionCategory.name == name)
    )
    if result.scalar_one_or_none() is not None:
        raise ConflictError(f"A category named '{name}' already exists.")

    # Get next display order
    max_order = await db.scalar(
        select(func.max(TransactionCategory.display_order))
    )
    next_order = (max_order or 0) + 1

    category = TransactionCategory(
        name=name,
        category_type=category_type,
        color=color,
        icon=icon,
        is_system=False,
        display_order=next_order,
        created_by=user.id,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession,
    category_id: uuid.UUID,
    **kwargs: object,
) -> TransactionCategory:
    result = await db.execute(
        select(TransactionCategory).where(TransactionCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError("TransactionCategory", str(category_id))

    name = kwargs.get("name")
    if name is not None:
        dup = await db.execute(
            select(TransactionCategory).where(
                TransactionCategory.name == name,
                TransactionCategory.id != category_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError(f"A category named '{name}' already exists.")

    for field, value in kwargs.items():
        if value is not None:
            setattr(category, field, value)

    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> None:
    result = await db.execute(
        select(TransactionCategory).where(TransactionCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError("TransactionCategory", str(category_id))
    if category.is_system:
        raise ForbiddenError("Cannot delete a system category.")

    await db.delete(category)
    await db.commit()


# ---------------------------------------------------------------------------
# Payment Account CRUD
# ---------------------------------------------------------------------------


async def create_account(
    db: AsyncSession,
    data: PaymentAccountCreate,
    user: User,
) -> PaymentAccount:
    account = PaymentAccount(
        user_id=user.id,
        name=data.name,
        account_type=data.account_type,
        opening_balance=data.opening_balance,
        opening_balance_date=data.opening_balance_date,
        default_tax_rate_id=data.default_tax_rate_id,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def list_accounts(db: AsyncSession, user_id: uuid.UUID) -> list[PaymentAccount]:
    result = await db.execute(
        select(PaymentAccount)
        .where(PaymentAccount.user_id == user_id, PaymentAccount.is_active.is_(True))
        .order_by(PaymentAccount.created_at)
    )
    return list(result.scalars().all())


async def get_account(db: AsyncSession, account_id: uuid.UUID) -> PaymentAccount:
    result = await db.execute(
        select(PaymentAccount).where(PaymentAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise NotFoundError("PaymentAccount", str(account_id))
    return account


async def update_account(
    db: AsyncSession,
    account_id: uuid.UUID,
    data: PaymentAccountUpdate,
) -> PaymentAccount:
    account = await get_account(db, account_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)
    await db.commit()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account_id: uuid.UUID) -> None:
    account = await get_account(db, account_id)
    account.is_active = False
    await db.commit()


async def get_account_current_balance(
    db: AsyncSession,
    account_id: uuid.UUID,
) -> float:
    """Calculate the current balance for an account."""
    account = await get_account(db, account_id)

    income_sum = await db.scalar(
        select(func.coalesce(func.sum(CashbookEntry.total_amount), 0.0)).where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.entry_type == EntryType.INCOME,
        )
    ) or 0.0

    expense_sum = await db.scalar(
        select(func.coalesce(func.sum(CashbookEntry.total_amount), 0.0)).where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.entry_type == EntryType.EXPENSE,
        )
    ) or 0.0

    return account.opening_balance + float(income_sum) - float(expense_sum)


# ---------------------------------------------------------------------------
# Cashbook Entry CRUD
# ---------------------------------------------------------------------------


async def _get_tax_rate_for_account(
    db: AsyncSession,
    account_id: uuid.UUID,
) -> float:
    """Get the default tax rate for an account. Returns 0 if none set."""
    account = await get_account(db, account_id)
    if account.default_tax_rate_id:
        from app.accounting.tax_models import TaxRate

        result = await db.execute(
            select(TaxRate).where(TaxRate.id == account.default_tax_rate_id)
        )
        tax_rate = result.scalar_one_or_none()
        if tax_rate and tax_rate.is_active:
            return tax_rate.rate
    return 0.0


async def create_entry(
    db: AsyncSession,
    data: CashbookEntryCreate,
    user: User,
) -> CashbookEntry:
    # Ensure account exists
    await get_account(db, data.account_id)

    # Ensure the accounting period is open
    from app.accounting.period_service import assert_period_open

    await assert_period_open(db, data.date)

    # Calculate tax
    tax_amount = data.tax_amount
    tax_rate_used: float | None = None
    tax_override = data.tax_override

    if not tax_override:
        tax_rate_used = await _get_tax_rate_for_account(db, data.account_id)
        if tax_rate_used > 0:
            tax_amount = calculate_tax(data.total_amount, tax_rate_used)
        else:
            tax_amount = None
    else:
        tax_rate_used = None

    entry = CashbookEntry(
        account_id=data.account_id,
        entry_type=data.entry_type,
        date=data.date,
        description=data.description,
        total_amount=data.total_amount,
        tax_amount=tax_amount,
        tax_rate_used=tax_rate_used,
        tax_override=tax_override,
        category_id=data.category_id,
        contact_id=data.contact_id,
        document_id=data.document_id,
        notes=data.notes,
        user_id=user.id,
        source="manual",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries(
    db: AsyncSession,
    filters: CashbookEntryFilter,
    pagination: PaginationParams,
) -> tuple[list[dict], dict]:
    """List entries with running balance computed per-account."""
    query = select(CashbookEntry).options(
        selectinload(CashbookEntry.category),
    )

    if filters.account_id is not None:
        query = query.where(CashbookEntry.account_id == filters.account_id)
    if filters.entry_type is not None:
        query = query.where(CashbookEntry.entry_type == filters.entry_type)
    if filters.category_id is not None:
        query = query.where(CashbookEntry.category_id == filters.category_id)
    if filters.date_from is not None:
        query = query.where(CashbookEntry.date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(CashbookEntry.date <= filters.date_to)
    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.where(CashbookEntry.description.ilike(search_term))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Order chronologically
    query = query.order_by(CashbookEntry.date.asc(), CashbookEntry.created_at.asc())
    query = query.offset(pagination.offset).limit(pagination.page_size)

    result = await db.execute(query)
    entries = list(result.scalars().unique().all())

    # Compute running balance for the page
    entries_with_balance = []
    if entries and filters.account_id:
        account = await get_account(db, filters.account_id)
        opening_balance = account.opening_balance

        # Sum all entries BEFORE the current page's first entry
        carry_forward_income = await db.scalar(
            select(func.coalesce(func.sum(CashbookEntry.total_amount), 0.0)).where(
                CashbookEntry.account_id == filters.account_id,
                CashbookEntry.entry_type == EntryType.INCOME,
                or_(
                    CashbookEntry.date < entries[0].date,
                    (CashbookEntry.date == entries[0].date)
                    & (CashbookEntry.created_at < entries[0].created_at),
                ),
            )
        ) or 0.0

        carry_forward_expense = await db.scalar(
            select(func.coalesce(func.sum(CashbookEntry.total_amount), 0.0)).where(
                CashbookEntry.account_id == filters.account_id,
                CashbookEntry.entry_type == EntryType.EXPENSE,
                or_(
                    CashbookEntry.date < entries[0].date,
                    (CashbookEntry.date == entries[0].date)
                    & (CashbookEntry.created_at < entries[0].created_at),
                ),
            )
        ) or 0.0

        running = opening_balance + float(carry_forward_income) - float(carry_forward_expense)

        for entry in entries:
            if entry.entry_type == EntryType.INCOME:
                running += entry.total_amount
            else:
                running -= entry.total_amount

            entry_dict = {
                "id": entry.id,
                "account_id": entry.account_id,
                "entry_type": entry.entry_type,
                "date": entry.date,
                "description": entry.description,
                "total_amount": entry.total_amount,
                "tax_amount": entry.tax_amount,
                "tax_rate_used": entry.tax_rate_used,
                "tax_override": entry.tax_override,
                "category_id": entry.category_id,
                "contact_id": entry.contact_id,
                "document_id": entry.document_id,
                "source": entry.source,
                "source_id": entry.source_id,
                "notes": entry.notes,
                "user_id": entry.user_id,
                "bank_balance": round(running, 2),
                "category": entry.category,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
            }
            entries_with_balance.append(entry_dict)
    else:
        for entry in entries:
            entry_dict = {
                "id": entry.id,
                "account_id": entry.account_id,
                "entry_type": entry.entry_type,
                "date": entry.date,
                "description": entry.description,
                "total_amount": entry.total_amount,
                "tax_amount": entry.tax_amount,
                "tax_rate_used": entry.tax_rate_used,
                "tax_override": entry.tax_override,
                "category_id": entry.category_id,
                "contact_id": entry.contact_id,
                "document_id": entry.document_id,
                "source": entry.source,
                "source_id": entry.source_id,
                "notes": entry.notes,
                "user_id": entry.user_id,
                "bank_balance": None,
                "category": entry.category,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
            }
            entries_with_balance.append(entry_dict)

    meta = build_pagination_meta(total_count, pagination)
    return entries_with_balance, meta


async def get_entry(db: AsyncSession, entry_id: uuid.UUID) -> CashbookEntry:
    result = await db.execute(
        select(CashbookEntry)
        .options(selectinload(CashbookEntry.category))
        .where(CashbookEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise NotFoundError("CashbookEntry", str(entry_id))
    return entry


async def update_entry(
    db: AsyncSession,
    entry_id: uuid.UUID,
    data: CashbookEntryUpdate,
    user: User,
) -> CashbookEntry:
    entry = await get_entry(db, entry_id)

    from app.accounting.period_service import assert_period_open

    await assert_period_open(db, entry.date)

    update_data = data.model_dump(exclude_unset=True)

    new_date = update_data.get("date")
    if new_date is not None and new_date != entry.date:
        await assert_period_open(db, new_date)

    for field, value in update_data.items():
        setattr(entry, field, value)

    # Recalculate tax if amount changed and not overridden
    if not entry.tax_override and "total_amount" in update_data:
        tax_rate = await _get_tax_rate_for_account(db, entry.account_id)
        if tax_rate > 0:
            entry.tax_amount = calculate_tax(entry.total_amount, tax_rate)
            entry.tax_rate_used = tax_rate

    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_entry(db: AsyncSession, entry_id: uuid.UUID) -> None:
    entry = await get_entry(db, entry_id)

    from app.accounting.period_service import assert_period_open

    await assert_period_open(db, entry.date)

    await db.delete(entry)
    await db.commit()


async def bulk_create_entries(
    db: AsyncSession,
    entries_data: list[dict],
    account_id: uuid.UUID,
    user: User,
) -> list[CashbookEntry]:
    """Bulk create entries (for Excel import)."""
    await get_account(db, account_id)

    created = []
    for row in entries_data:
        entry = CashbookEntry(
            account_id=account_id,
            entry_type=EntryType(row["entry_type"]),
            date=row["date"],
            description=row["description"],
            total_amount=row["total_amount"],
            tax_amount=row.get("tax_amount"),
            tax_rate_used=row.get("tax_rate_used"),
            tax_override=False,
            category_id=row.get("category_id"),
            notes=row.get("notes"),
            user_id=user.id,
            source="excel_import",
            source_id=row.get("source_id"),
        )
        db.add(entry)
        created.append(entry)

    await db.commit()
    for entry in created:
        await db.refresh(entry)

    return created


# ---------------------------------------------------------------------------
# Summary / Aggregation
# ---------------------------------------------------------------------------


async def get_summary(
    db: AsyncSession,
    account_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Get category totals and balance summary for a date range."""
    account = await get_account(db, account_id)

    # Income total
    total_income = await db.scalar(
        select(func.coalesce(func.sum(CashbookEntry.total_amount), 0.0)).where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.entry_type == EntryType.INCOME,
            CashbookEntry.date.between(date_from, date_to),
        )
    ) or 0.0

    # Expense total
    total_expenses = await db.scalar(
        select(func.coalesce(func.sum(CashbookEntry.total_amount), 0.0)).where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.entry_type == EntryType.EXPENSE,
            CashbookEntry.date.between(date_from, date_to),
        )
    ) or 0.0

    # Tax collected (income entries)
    total_tax_collected = await db.scalar(
        select(func.coalesce(func.sum(CashbookEntry.tax_amount), 0.0)).where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.entry_type == EntryType.INCOME,
            CashbookEntry.date.between(date_from, date_to),
            CashbookEntry.tax_amount.isnot(None),
        )
    ) or 0.0

    # Tax paid (expense entries)
    total_tax_paid = await db.scalar(
        select(func.coalesce(func.sum(CashbookEntry.tax_amount), 0.0)).where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.entry_type == EntryType.EXPENSE,
            CashbookEntry.date.between(date_from, date_to),
            CashbookEntry.tax_amount.isnot(None),
        )
    ) or 0.0

    # Entries before the period for opening balance
    pre_income = await db.scalar(
        select(func.coalesce(func.sum(CashbookEntry.total_amount), 0.0)).where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.entry_type == EntryType.INCOME,
            CashbookEntry.date < date_from,
        )
    ) or 0.0

    pre_expense = await db.scalar(
        select(func.coalesce(func.sum(CashbookEntry.total_amount), 0.0)).where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.entry_type == EntryType.EXPENSE,
            CashbookEntry.date < date_from,
        )
    ) or 0.0

    opening_balance = account.opening_balance + float(pre_income) - float(pre_expense)
    net_change = float(total_income) - float(total_expenses)
    closing_balance = opening_balance + net_change

    # Category totals
    category_query = (
        select(
            TransactionCategory.id.label("category_id"),
            TransactionCategory.name.label("category_name"),
            TransactionCategory.category_type.label("cat_type"),
            CashbookEntry.entry_type,
            func.sum(CashbookEntry.total_amount).label("total_amount"),
            func.coalesce(func.sum(CashbookEntry.tax_amount), 0.0).label("total_tax"),
            func.count(CashbookEntry.id).label("count"),
        )
        .outerjoin(TransactionCategory, CashbookEntry.category_id == TransactionCategory.id)
        .where(
            CashbookEntry.account_id == account_id,
            CashbookEntry.date.between(date_from, date_to),
        )
        .group_by(
            TransactionCategory.id,
            TransactionCategory.name,
            TransactionCategory.category_type,
            CashbookEntry.entry_type,
        )
        .order_by(func.sum(CashbookEntry.total_amount).desc())
    )

    cat_result = await db.execute(category_query)
    category_totals = [
        CategoryTotal(
            category_id=row.category_id,
            category_name=row.category_name or "Uncategorized",
            category_type=row.cat_type,
            entry_type=row.entry_type,
            total_amount=float(row.total_amount or 0),
            total_tax=float(row.total_tax or 0),
            count=row.count,
        )
        for row in cat_result.all()
    ]

    return {
        "opening_balance": round(opening_balance, 2),
        "closing_balance": round(closing_balance, 2),
        "total_income": round(float(total_income), 2),
        "total_expenses": round(float(total_expenses), 2),
        "net_change": round(net_change, 2),
        "total_tax_collected": round(float(total_tax_collected), 2),
        "total_tax_paid": round(float(total_tax_paid), 2),
        "category_totals": category_totals,
        "period_start": date_from,
        "period_end": date_to,
    }


# ---------------------------------------------------------------------------
# Document Capture → Cashbook Entry
# ---------------------------------------------------------------------------

# Maps AI extraction categories to TransactionCategory names
AI_TO_TRANSACTION_CATEGORY: dict[str, dict[str, str]] = {
    "food_dining": {"expense": "Meals", "income": "Other Income"},
    "transportation": {"expense": "Vehicle Fuel", "income": "Other Income"},
    "office_supplies": {"expense": "Office Supplies", "income": "Other Income"},
    "travel": {"expense": "Travel", "income": "Other Income"},
    "utilities": {"expense": "Utilities", "income": "Other Income"},
    "insurance": {"expense": "Insurance General", "income": "Other Income"},
    "professional_services": {"expense": "Professional Fees", "income": "Fees"},
    "software_subscriptions": {"expense": "Dues & Subscriptions", "income": "Other Income"},
    "marketing": {"expense": "Advertising", "income": "Other Income"},
    "equipment": {"expense": "Repairs & Maintenance", "income": "Other Income"},
    "taxes": {"expense": "HST/GST Paid", "income": "HST/GST Collected"},
    "entertainment": {"expense": "Meals & Entertainment", "income": "Other Income"},
    "healthcare": {"expense": "Other Expense", "income": "Other Income"},
    "education": {"expense": "Education & Training", "income": "Other Income"},
    "other": {"expense": "Other Expense", "income": "Other Income"},
}


async def _create_entry_from_extraction(
    db: AsyncSession,
    document: "Document",
    extraction: dict,
    entry_type: EntryType,
    account_id: uuid.UUID,
    user: User,
) -> CashbookEntry:
    """Create a CashbookEntry from AI-extracted metadata."""
    # Map AI category to TransactionCategory
    category_id = None
    ai_category = extraction.get("category")
    if ai_category:
        mapping = AI_TO_TRANSACTION_CATEGORY.get(ai_category, {})
        target_name = mapping.get(entry_type.value)
        if target_name:
            result = await db.execute(
                select(TransactionCategory).where(
                    TransactionCategory.name == target_name
                )
            )
            cat = result.scalar_one_or_none()
            if cat:
                category_id = cat.id

    # Parse date
    entry_date = date.today()
    date_str = extraction.get("date")
    if date_str:
        try:
            entry_date = date.fromisoformat(date_str)
        except ValueError:
            pass

    # Build description
    vendor = extraction.get("vendor_name") or ""
    description = vendor or f"From {document.title or document.original_filename}"
    if len(description) > 500:
        description = description[:497] + "..."

    # Determine tax handling
    tax_amount = extraction.get("tax_amount")
    tax_override = tax_amount is not None

    entry_data = CashbookEntryCreate(
        account_id=account_id,
        entry_type=entry_type,
        date=entry_date,
        description=description,
        total_amount=extraction["total_amount"],
        tax_amount=tax_amount,
        tax_override=tax_override,
        category_id=category_id,
        document_id=document.id,
    )

    return await create_entry(db, entry_data, user)


async def capture_and_book(
    db: AsyncSession,
    storage: "StorageBackend",
    file_data: bytes,
    filename: str,
    content_type: str,
    user: User,
    settings: object,
    entry_type: EntryType,
    account_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
) -> tuple["Document", dict | None, CashbookEntry | None, int]:
    """Upload a document, extract data with AI, and create a cashbook entry.

    Each step is independent: if AI fails the document is still saved,
    and if entry creation fails the document + extraction are still saved.
    """
    from app.documents.service import upload_document

    start = time.monotonic()

    # Step 1: Upload the document
    doc_type = "receipt" if entry_type == EntryType.EXPENSE else "invoice"
    document = await upload_document(
        db=db,
        storage=storage,
        file_data=file_data,
        filename=filename,
        content_type=content_type,
        user=user,
        folder_id=folder_id,
        settings=settings,
        document_type=doc_type,
        title=None,
    )

    extraction_dict: dict | None = None
    entry: CashbookEntry | None = None

    # Step 2: AI extraction (synchronous, not background)
    extractable_types = {
        "image/png", "image/jpeg", "image/webp", "image/gif", "application/pdf",
    }
    if content_type in extractable_types and getattr(settings, "anthropic_api_key", None):
        try:
            from app.ai.service import process_document_ai

            _doc, extraction_result = await process_document_ai(
                db, storage, document.id, settings,
            )
            extraction_dict = extraction_result.model_dump(mode="json")
        except Exception:
            logger.warning(
                "Cashbook capture: AI extraction failed for document %s",
                document.id,
                exc_info=True,
            )

    # Step 3: Create cashbook entry from extraction
    if extraction_dict and extraction_dict.get("total_amount"):
        try:
            entry = await _create_entry_from_extraction(
                db=db,
                document=document,
                extraction=extraction_dict,
                entry_type=entry_type,
                account_id=account_id,
                user=user,
            )
        except Exception:
            logger.warning(
                "Cashbook capture: entry creation failed for document %s",
                document.id,
                exc_info=True,
            )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return document, extraction_dict, entry, elapsed_ms
