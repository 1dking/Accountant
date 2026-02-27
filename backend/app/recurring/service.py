from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.recurring.models import Frequency, RecurringRule, RecurringType
from app.recurring.schemas import RecurringRuleCreate, RecurringRuleUpdate


def advance_date(current: date, frequency: Frequency) -> date:
    if frequency == Frequency.WEEKLY:
        return current + timedelta(weeks=1)
    if frequency == Frequency.BIWEEKLY:
        return current + timedelta(weeks=2)
    if frequency == Frequency.MONTHLY:
        return current + relativedelta(months=1)
    if frequency == Frequency.QUARTERLY:
        return current + relativedelta(months=3)
    if frequency == Frequency.YEARLY:
        return current + relativedelta(years=1)
    return current + relativedelta(months=1)


async def create_rule(
    db: AsyncSession, data: RecurringRuleCreate, user: User
) -> RecurringRule:
    rule = RecurringRule(
        type=data.type,
        name=data.name,
        frequency=data.frequency,
        next_run_date=data.next_run_date,
        end_date=data.end_date,
        template_data=json.dumps(data.template_data),
        created_by=user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def list_rules(
    db: AsyncSession, pagination: PaginationParams
) -> tuple[list[RecurringRule], dict]:
    from sqlalchemy import func

    count_q = select(func.count(RecurringRule.id))
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(RecurringRule)
        .order_by(RecurringRule.next_run_date)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(query)
    rules = list(result.scalars().all())

    return rules, build_pagination_meta(total, pagination)


async def get_rule(db: AsyncSession, rule_id: uuid.UUID) -> RecurringRule:
    result = await db.execute(select(RecurringRule).where(RecurringRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise NotFoundError("RecurringRule", str(rule_id))
    return rule


async def update_rule(
    db: AsyncSession, rule_id: uuid.UUID, data: RecurringRuleUpdate, user: User
) -> RecurringRule:
    rule = await get_rule(db, rule_id)
    update_data = data.model_dump(exclude_unset=True)
    if "template_data" in update_data and update_data["template_data"] is not None:
        update_data["template_data"] = json.dumps(update_data["template_data"])
    for key, value in update_data.items():
        setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule_id: uuid.UUID) -> None:
    rule = await get_rule(db, rule_id)
    await db.delete(rule)
    await db.commit()


async def toggle_rule(db: AsyncSession, rule_id: uuid.UUID) -> RecurringRule:
    rule = await get_rule(db, rule_id)
    rule.is_active = not rule.is_active
    await db.commit()
    await db.refresh(rule)
    return rule


async def process_recurring_rules(db: AsyncSession) -> int:
    """Process all due recurring rules. Returns number of transactions created."""
    today = date.today()
    result = await db.execute(
        select(RecurringRule).where(
            RecurringRule.is_active == True,  # noqa: E712
            RecurringRule.next_run_date <= today,
        )
    )
    rules = result.scalars().all()
    count = 0

    for rule in rules:
        if rule.end_date and rule.next_run_date > rule.end_date:
            rule.is_active = False
            continue

        template = json.loads(rule.template_data)

        # Get the user who created the rule
        user_result = await db.execute(select(User).where(User.id == rule.created_by))
        user = user_result.scalar_one_or_none()
        if not user:
            continue

        try:
            if rule.type == RecurringType.EXPENSE:
                from app.accounting.schemas import ExpenseCreate
                from app.accounting.service import create_expense

                template["date"] = today.isoformat()
                expense_data = ExpenseCreate(**template)
                await create_expense(db, expense_data, user)

            elif rule.type == RecurringType.INCOME:
                from app.income.schemas import IncomeCreate
                from app.income.service import create_income

                template["date"] = today.isoformat()
                income_data = IncomeCreate(**template)
                await create_income(db, income_data, user)

            elif rule.type == RecurringType.INVOICE:
                from app.invoicing.schemas import InvoiceCreate
                from app.invoicing.service import create_invoice

                template["issue_date"] = today.isoformat()
                if "due_days" in template:
                    due_days = template.pop("due_days")
                    template["due_date"] = (today + timedelta(days=due_days)).isoformat()
                elif "due_date" not in template:
                    template["due_date"] = (today + timedelta(days=30)).isoformat()
                invoice_data = InvoiceCreate(**template)
                await create_invoice(db, invoice_data, user)

            count += 1
        except Exception:
            continue

        rule.last_run_date = today
        rule.run_count += 1
        rule.next_run_date = advance_date(rule.next_run_date, rule.frequency)

        if rule.end_date and rule.next_run_date > rule.end_date:
            rule.is_active = False

    await db.commit()
    return count


async def get_upcoming_rules(db: AsyncSession, days: int = 30) -> list[RecurringRule]:
    from datetime import timedelta

    cutoff = date.today() + timedelta(days=days)
    result = await db.execute(
        select(RecurringRule)
        .where(
            RecurringRule.is_active == True,  # noqa: E712
            RecurringRule.next_run_date <= cutoff,
        )
        .order_by(RecurringRule.next_run_date)
    )
    return list(result.scalars().all())
