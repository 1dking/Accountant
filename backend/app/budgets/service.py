from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense, ExpenseCategory
from app.auth.models import User
from app.budgets.models import Budget, PeriodType
from app.budgets.schemas import BudgetCreate, BudgetUpdate, BudgetVsActual
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta


async def create_budget(
    db: AsyncSession, data: BudgetCreate, user: User
) -> Budget:
    # Check for duplicate
    q = select(Budget).where(
        Budget.category_id == data.category_id,
        Budget.period_type == data.period_type,
        Budget.year == data.year,
        Budget.month == data.month,
    )
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing:
        raise ConflictError("A budget already exists for this category/period combination.")

    budget = Budget(
        **data.model_dump(),
        created_by=user.id,
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


async def list_budgets(
    db: AsyncSession,
    year: int | None,
    period_type: PeriodType | None,
    pagination: PaginationParams,
) -> tuple[list[Budget], dict]:
    query = select(Budget)
    if year is not None:
        query = query.where(Budget.year == year)
    if period_type is not None:
        query = query.where(Budget.period_type == period_type)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Budget.year.desc(), Budget.month).offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    budgets = list(result.scalars().all())

    return budgets, build_pagination_meta(total, pagination)


async def get_budget(db: AsyncSession, budget_id: uuid.UUID) -> Budget:
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if budget is None:
        raise NotFoundError("Budget", str(budget_id))
    return budget


async def update_budget(
    db: AsyncSession, budget_id: uuid.UUID, data: BudgetUpdate, user: User
) -> Budget:
    budget = await get_budget(db, budget_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(budget, key, value)
    await db.commit()
    await db.refresh(budget)
    return budget


async def delete_budget(db: AsyncSession, budget_id: uuid.UUID) -> None:
    budget = await get_budget(db, budget_id)
    await db.delete(budget)
    await db.commit()


async def get_budget_vs_actual(
    db: AsyncSession, year: int, month: int | None = None
) -> list[BudgetVsActual]:
    # Get all matching budgets
    budget_q = select(Budget).where(Budget.year == year)
    if month is not None:
        budget_q = budget_q.where(
            (Budget.month == month) | (Budget.month.is_(None))
        )
    budget_result = await db.execute(budget_q)
    budgets = budget_result.scalars().all()

    results = []
    for budget in budgets:
        # Build expense filter based on budget period
        expense_q = select(func.coalesce(func.sum(Expense.amount), 0))
        expense_q = expense_q.where(extract("year", Expense.date) == year)

        if budget.period_type == PeriodType.MONTHLY and budget.month:
            expense_q = expense_q.where(extract("month", Expense.date) == budget.month)
        elif budget.period_type == PeriodType.QUARTERLY and budget.month:
            quarter_start = ((budget.month - 1) // 3) * 3 + 1
            expense_q = expense_q.where(
                extract("month", Expense.date).between(quarter_start, quarter_start + 2)
            )

        if budget.category_id:
            expense_q = expense_q.where(Expense.category_id == budget.category_id)

        actual = float((await db.execute(expense_q)).scalar() or 0)

        # Get category name
        cat_name = "Overall"
        if budget.category_id:
            cat_result = await db.execute(
                select(ExpenseCategory.name).where(ExpenseCategory.id == budget.category_id)
            )
            cat_name = cat_result.scalar() or "Unknown"

        results.append(BudgetVsActual(
            budget_id=budget.id,
            budget_name=budget.name,
            category_id=budget.category_id,
            category_name=cat_name,
            budgeted_amount=budget.amount,
            actual_amount=actual,
            remaining=budget.amount - actual,
            percentage_used=round((actual / budget.amount) * 100, 1) if budget.amount > 0 else 0,
        ))

    return results


async def get_budget_alerts(db: AsyncSession) -> list[BudgetVsActual]:
    today = date.today()
    comparisons = await get_budget_vs_actual(db, today.year, today.month)
    return [c for c in comparisons if c.percentage_used >= 80]
