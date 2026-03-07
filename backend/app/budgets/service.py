
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense, ExpenseCategory
from app.auth.models import User
from app.budgets.models import Budget, PeriodType
from app.budgets.schemas import BudgetCreate, BudgetUpdate, BudgetVsActual
from app.collaboration.service import log_activity
from app.core.authorization import apply_ownership_filter, authorize_owner
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

    await log_activity(
        db,
        user_id=user.id,
        action="budget_created",
        resource_type="budget",
        resource_id=str(budget.id),
        details={"name": budget.name, "amount": budget.amount, "year": budget.year},
    )

    return budget


async def list_budgets(
    db: AsyncSession,
    year: int | None,
    period_type: PeriodType | None,
    pagination: PaginationParams,
    user: User,
) -> tuple[list[Budget], dict]:
    query = select(Budget)
    query = apply_ownership_filter(query, Budget.created_by, user)
    if year is not None:
        query = query.where(Budget.year == year)
    if period_type is not None:
        query = query.where(Budget.period_type == period_type)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        query.order_by(Budget.year.desc(), Budget.month)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(query)
    budgets = list(result.scalars().all())

    return budgets, build_pagination_meta(total, pagination)


async def get_budget(db: AsyncSession, budget_id: uuid.UUID, user: User | None = None) -> Budget:
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if budget is None:
        raise NotFoundError("Budget", str(budget_id))
    if user is not None:
        authorize_owner(budget.created_by, user, "Budget")
    return budget


async def update_budget(
    db: AsyncSession, budget_id: uuid.UUID, data: BudgetUpdate, user: User
) -> Budget:
    budget = await get_budget(db, budget_id, user)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(budget, key, value)
    await db.commit()
    await db.refresh(budget)

    await log_activity(
        db,
        user_id=user.id,
        action="budget_updated",
        resource_type="budget",
        resource_id=str(budget.id),
        details={"name": budget.name, "amount": budget.amount},
    )

    return budget


async def delete_budget(db: AsyncSession, budget_id: uuid.UUID, user: User) -> None:
    budget = await get_budget(db, budget_id, user)
    await db.delete(budget)
    await db.commit()


async def get_budget_vs_actual(
    db: AsyncSession, year: int, month: int | None = None, user: User | None = None,
) -> list[BudgetVsActual]:
    # Get all matching budgets
    budget_q = select(Budget).where(Budget.year == year)
    if user is not None:
        budget_q = apply_ownership_filter(budget_q, Budget.created_by, user)
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

        actual_raw = (await db.execute(expense_q)).scalar() or 0
        actual = Decimal(str(actual_raw))

        # Get category name
        cat_name = "Overall"
        if budget.category_id:
            cat_result = await db.execute(
                select(ExpenseCategory.name).where(ExpenseCategory.id == budget.category_id)
            )
            cat_name = cat_result.scalar() or "Unknown"

        budgeted = Decimal(str(budget.amount))
        remaining = budgeted - actual
        percentage_used = (actual / budgeted * Decimal('100')).quantize(Decimal('0.1')) if budgeted > 0 else Decimal('0')

        results.append(BudgetVsActual(
            budget_id=budget.id,
            budget_name=budget.name,
            category_id=budget.category_id,
            category_name=cat_name,
            budgeted_amount=budgeted,
            actual_amount=actual,
            remaining=remaining,
            percentage_used=percentage_used,
        ))

    return results


async def get_budget_alerts(db: AsyncSession, user: User | None = None) -> list[BudgetVsActual]:
    today = date.today()
    comparisons = await get_budget_vs_actual(db, today.year, today.month, user=user)
    return [c for c in comparisons if c.percentage_used >= 80]
