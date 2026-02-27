
from typing import Optional

import uuid
from datetime import date

from sqlalchemy import extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.income.models import Income, IncomeCategory
from app.income.schemas import (
    IncomeCategorySummary,
    IncomeCreate,
    IncomeFilter,
    IncomeMonthSummary,
    IncomeSummary,
    IncomeUpdate,
)


async def create_income(
    db: AsyncSession, data: IncomeCreate, user: User
) -> Income:
    income = Income(
        **data.model_dump(),
        created_by=user.id,
    )
    db.add(income)
    await db.commit()
    await db.refresh(income)
    return income


async def create_income_from_payment(
    db: AsyncSession, invoice, payment, user: User
) -> Income:
    """Auto-create an income entry when an invoice payment is recorded."""
    income = Income(
        contact_id=invoice.contact_id,
        invoice_id=invoice.id,
        category=IncomeCategory.INVOICE_PAYMENT,
        description=f"Payment for invoice {invoice.invoice_number}",
        amount=payment.amount,
        currency=invoice.currency,
        date=payment.date,
        payment_method=payment.payment_method,
        reference=payment.reference,
        created_by=user.id,
    )
    db.add(income)
    await db.commit()
    await db.refresh(income)
    return income


async def list_income(
    db: AsyncSession, filters: IncomeFilter, pagination: PaginationParams
) -> tuple[list[Income], dict]:
    query = select(Income)

    if filters.search:
        term = f"%{filters.search}%"
        query = query.where(
            or_(
                Income.description.ilike(term),
                Income.reference.ilike(term),
            )
        )
    if filters.category is not None:
        query = query.where(Income.category == filters.category)
    if filters.contact_id is not None:
        query = query.where(Income.contact_id == filters.contact_id)
    if filters.date_from is not None:
        query = query.where(Income.date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Income.date <= filters.date_to)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Income.date.desc()).offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    entries = list(result.scalars().all())

    return entries, build_pagination_meta(total, pagination)


async def get_income(db: AsyncSession, income_id: uuid.UUID) -> Income:
    result = await db.execute(select(Income).where(Income.id == income_id))
    income = result.scalar_one_or_none()
    if income is None:
        raise NotFoundError("Income", str(income_id))
    return income


async def update_income(
    db: AsyncSession, income_id: uuid.UUID, data: IncomeUpdate, user: User
) -> Income:
    income = await get_income(db, income_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(income, key, value)
    await db.commit()
    await db.refresh(income)
    return income


async def delete_income(db: AsyncSession, income_id: uuid.UUID) -> None:
    income = await get_income(db, income_id)
    await db.delete(income)
    await db.commit()


async def get_income_summary(
    db: AsyncSession, date_from: Optional[date] = None, date_to: Optional[date] = None
) -> IncomeSummary:
    base = select(Income)
    if date_from:
        base = base.where(Income.date >= date_from)
    if date_to:
        base = base.where(Income.date <= date_to)

    # Total
    total_q = select(
        func.coalesce(func.sum(Income.amount), 0),
        func.count(Income.id),
    ).select_from(base.subquery())
    row = (await db.execute(total_q)).one()
    total_amount = float(row[0])
    income_count = row[1]

    # By category
    cat_q = (
        select(Income.category, func.sum(Income.amount), func.count(Income.id))
        .group_by(Income.category)
    )
    if date_from:
        cat_q = cat_q.where(Income.date >= date_from)
    if date_to:
        cat_q = cat_q.where(Income.date <= date_to)
    cat_rows = (await db.execute(cat_q)).all()
    by_category = [
        IncomeCategorySummary(category=r[0].value, total=float(r[1]), count=r[2])
        for r in cat_rows
    ]

    # By month
    month_q = (
        select(
            extract("year", Income.date).label("y"),
            extract("month", Income.date).label("m"),
            func.sum(Income.amount),
            func.count(Income.id),
        )
        .group_by("y", "m")
        .order_by("y", "m")
    )
    if date_from:
        month_q = month_q.where(Income.date >= date_from)
    if date_to:
        month_q = month_q.where(Income.date <= date_to)
    month_rows = (await db.execute(month_q)).all()
    by_month = [
        IncomeMonthSummary(year=int(r[0]), month=int(r[1]), total=float(r[2]), count=r[3])
        for r in month_rows
    ]

    return IncomeSummary(
        total_amount=total_amount,
        income_count=income_count,
        by_category=by_category,
        by_month=by_month,
    )
