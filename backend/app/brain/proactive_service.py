"""Proactive insights — daily background job + alert generation."""

import json
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.models import ProactiveAlert, AlertType
from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


async def generate_daily_briefing(db: AsyncSession, user_id: uuid.UUID) -> list[ProactiveAlert]:
    """Generate daily proactive alerts for a user. Called by background job."""
    alerts: list[ProactiveAlert] = []

    try:
        alerts.extend(await _check_overdue_invoices(db, user_id))
    except Exception as e:
        logger.error(f"Overdue invoices check failed: {e}")

    try:
        alerts.extend(await _check_upcoming_deadlines(db, user_id))
    except Exception as e:
        logger.error(f"Upcoming deadlines check failed: {e}")

    try:
        alerts.extend(await _check_revenue_trends(db, user_id))
    except Exception as e:
        logger.error(f"Revenue trends check failed: {e}")

    try:
        alerts.extend(await _check_expense_anomalies(db, user_id))
    except Exception as e:
        logger.error(f"Expense anomaly check failed: {e}")

    try:
        alerts.extend(await _check_follow_up_reminders(db, user_id))
    except Exception as e:
        logger.error(f"Follow-up reminders check failed: {e}")

    try:
        alerts.extend(await _check_cashflow_forecast(db, user_id))
    except Exception as e:
        logger.error(f"Cashflow forecast check failed: {e}")

    # Save all alerts
    for alert in alerts:
        db.add(alert)
    if alerts:
        await db.commit()

    return alerts


async def _check_overdue_invoices(db: AsyncSession, user_id: uuid.UUID) -> list[ProactiveAlert]:
    """Check for overdue/upcoming invoices."""
    from app.invoices.models import Invoice

    alerts = []
    now = datetime.utcnow()

    # Overdue invoices
    overdue_stmt = select(func.count(), func.sum(Invoice.total)).where(
        and_(
            Invoice.status.in_(["sent", "viewed"]),
            Invoice.due_date < now.date(),
        )
    )
    result = await db.execute(overdue_stmt)
    row = result.one()
    overdue_count = row[0] or 0
    overdue_total = float(row[1] or 0)

    if overdue_count > 0:
        alerts.append(ProactiveAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            alert_type=AlertType.OVERDUE_INVOICE,
            title=f"{overdue_count} overdue invoice{'s' if overdue_count > 1 else ''}",
            message=f"You have {overdue_count} overdue invoice{'s' if overdue_count > 1 else ''} totaling ${overdue_total:,.2f}. Consider sending payment reminders.",
            data_json=json.dumps({"count": overdue_count, "total": overdue_total}),
        ))

    # Invoices due in next 3 days
    upcoming_stmt = select(func.count(), func.sum(Invoice.total)).where(
        and_(
            Invoice.status.in_(["sent", "viewed"]),
            Invoice.due_date >= now.date(),
            Invoice.due_date <= (now + timedelta(days=3)).date(),
        )
    )
    result = await db.execute(upcoming_stmt)
    row = result.one()
    upcoming_count = row[0] or 0
    upcoming_total = float(row[1] or 0)

    if upcoming_count > 0:
        alerts.append(ProactiveAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            alert_type=AlertType.UPCOMING_DEADLINE,
            title=f"{upcoming_count} invoice{'s' if upcoming_count > 1 else ''} due soon",
            message=f"{upcoming_count} invoice{'s' if upcoming_count > 1 else ''} worth ${upcoming_total:,.2f} {'are' if upcoming_count > 1 else 'is'} due in the next 3 days.",
            data_json=json.dumps({"count": upcoming_count, "total": upcoming_total}),
        ))

    return alerts


async def _check_upcoming_deadlines(db: AsyncSession, user_id: uuid.UUID) -> list[ProactiveAlert]:
    """Check for upcoming calendar events and meetings."""
    from app.calendar.models import CalendarEvent

    alerts = []
    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)

    stmt = select(func.count()).where(
        and_(
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= tomorrow,
        )
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0

    if count > 0:
        alerts.append(ProactiveAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            alert_type=AlertType.UPCOMING_DEADLINE,
            title=f"{count} event{'s' if count > 1 else ''} in the next 24 hours",
            message=f"You have {count} upcoming event{'s' if count > 1 else ''} scheduled. Check your calendar to prepare.",
            data_json=json.dumps({"count": count}),
        ))

    return alerts


async def _check_revenue_trends(db: AsyncSession, user_id: uuid.UUID) -> list[ProactiveAlert]:
    """Compare this month's revenue vs last month."""
    from app.accounting.models import Income

    alerts = []
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    # This month revenue
    this_stmt = select(func.sum(Income.amount)).where(
        Income.date >= this_month_start.date()
    )
    result = await db.execute(this_stmt)
    this_revenue = float(result.scalar() or 0)

    # Last month revenue (prorated to same day)
    last_stmt = select(func.sum(Income.amount)).where(
        and_(
            Income.date >= last_month_start.date(),
            Income.date < this_month_start.date(),
        )
    )
    result = await db.execute(last_stmt)
    last_revenue = float(result.scalar() or 0)

    if last_revenue > 0:
        day_of_month = now.day
        # Prorate last month to comparable period
        import calendar
        _, last_month_days = calendar.monthrange(last_month_start.year, last_month_start.month)
        prorated_last = last_revenue * (day_of_month / last_month_days)

        if prorated_last > 0:
            change_pct = ((this_revenue - prorated_last) / prorated_last) * 100
            if change_pct >= 20:
                alerts.append(ProactiveAlert(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    alert_type=AlertType.REVENUE_MILESTONE,
                    title="Revenue is trending up!",
                    message=f"Revenue this month (${this_revenue:,.2f}) is {change_pct:.0f}% ahead of last month's pace.",
                    data_json=json.dumps({
                        "this_month": this_revenue,
                        "last_month_prorated": prorated_last,
                        "change_pct": round(change_pct, 1),
                    }),
                ))
            elif change_pct <= -20:
                alerts.append(ProactiveAlert(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    alert_type=AlertType.REVENUE_MILESTONE,
                    title="Revenue is trending down",
                    message=f"Revenue this month (${this_revenue:,.2f}) is {abs(change_pct):.0f}% behind last month's pace.",
                    data_json=json.dumps({
                        "this_month": this_revenue,
                        "last_month_prorated": prorated_last,
                        "change_pct": round(change_pct, 1),
                    }),
                ))

    return alerts


async def _check_expense_anomalies(db: AsyncSession, user_id: uuid.UUID) -> list[ProactiveAlert]:
    """Check for unusual expense patterns."""
    from app.accounting.models import Expense

    alerts = []
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    # Large recent expenses (> 3x average)
    avg_stmt = select(func.avg(Expense.amount)).where(
        Expense.date >= (now - timedelta(days=90)).date()
    )
    result = await db.execute(avg_stmt)
    avg_expense = float(result.scalar() or 0)

    if avg_expense > 0:
        large_stmt = select(func.count(), func.sum(Expense.amount)).where(
            and_(
                Expense.date >= seven_days_ago.date(),
                Expense.amount > avg_expense * 3,
            )
        )
        result = await db.execute(large_stmt)
        row = result.one()
        large_count = row[0] or 0
        large_total = float(row[1] or 0)

        if large_count > 0:
            alerts.append(ProactiveAlert(
                id=uuid.uuid4(),
                user_id=user_id,
                alert_type=AlertType.EXPENSE_ANOMALY,
                title=f"{large_count} unusually large expense{'s' if large_count > 1 else ''}",
                message=f"Found {large_count} expense{'s' if large_count > 1 else ''} this week (${large_total:,.2f}) that {'are' if large_count > 1 else 'is'} more than 3x your average.",
                data_json=json.dumps({
                    "count": large_count,
                    "total": large_total,
                    "avg_expense": round(avg_expense, 2),
                }),
            ))

    return alerts


async def _check_follow_up_reminders(db: AsyncSession, user_id: uuid.UUID) -> list[ProactiveAlert]:
    """Check for contacts/proposals needing follow-up."""
    from app.proposals.models import Proposal

    alerts = []
    now = datetime.utcnow()
    stale_date = now - timedelta(days=7)

    # Proposals sent > 7 days ago with no response
    stmt = select(func.count()).where(
        and_(
            Proposal.status == "sent",
            Proposal.sent_at is not None,
            Proposal.sent_at <= stale_date,
        )
    )
    result = await db.execute(stmt)
    stale_count = result.scalar() or 0

    if stale_count > 0:
        alerts.append(ProactiveAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            alert_type=AlertType.FOLLOW_UP_NEEDED,
            title=f"{stale_count} proposal{'s' if stale_count > 1 else ''} need follow-up",
            message=f"{stale_count} proposal{'s' if stale_count > 1 else ''} sent over a week ago with no response. Consider following up.",
            data_json=json.dumps({"count": stale_count}),
        ))

    return alerts


async def _check_cashflow_forecast(db: AsyncSession, user_id: uuid.UUID) -> list[ProactiveAlert]:
    """Simple cashflow forecast based on recurring rules."""
    from app.accounting.models import Expense, Income

    alerts = []
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # This month's income and expenses
    income_stmt = select(func.sum(Income.amount)).where(
        Income.date >= month_start.date()
    )
    expense_stmt = select(func.sum(Expense.amount)).where(
        Expense.date >= month_start.date()
    )

    income_result = await db.execute(income_stmt)
    expense_result = await db.execute(expense_stmt)

    total_income = float(income_result.scalar() or 0)
    total_expenses = float(expense_result.scalar() or 0)
    net = total_income - total_expenses

    if net < 0 and abs(net) > 1000:
        alerts.append(ProactiveAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            alert_type=AlertType.CASHFLOW_WARNING,
            title="Negative cash flow this month",
            message=f"Expenses exceed income by ${abs(net):,.2f} this month. Review your spending or follow up on outstanding invoices.",
            data_json=json.dumps({
                "income": total_income,
                "expenses": total_expenses,
                "net": net,
            }),
        ))

    return alerts


# ── Alert management ──────────────────────────────────────────────────

async def list_alerts(
    db: AsyncSession,
    user_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 20,
) -> list[ProactiveAlert]:
    """List alerts for a user."""
    stmt = select(ProactiveAlert).where(ProactiveAlert.user_id == user_id)
    if unread_only:
        stmt = stmt.where(ProactiveAlert.is_read == False)  # noqa: E712
    stmt = stmt.order_by(ProactiveAlert.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_alert_read(db: AsyncSession, alert_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Mark an alert as read."""
    stmt = select(ProactiveAlert).where(
        and_(ProactiveAlert.id == alert_id, ProactiveAlert.user_id == user_id)
    )
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        return False
    alert.is_read = True
    await db.commit()
    return True


async def mark_all_alerts_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Mark all alerts as read. Returns count."""
    stmt = select(ProactiveAlert).where(
        and_(ProactiveAlert.user_id == user_id, ProactiveAlert.is_read == False)  # noqa: E712
    )
    result = await db.execute(stmt)
    alerts = list(result.scalars().all())
    for alert in alerts:
        alert.is_read = True
    await db.commit()
    return len(alerts)


async def get_daily_briefing(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Get today's briefing summary."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(ProactiveAlert).where(
        and_(
            ProactiveAlert.user_id == user_id,
            ProactiveAlert.created_at >= today,
        )
    ).order_by(ProactiveAlert.created_at.desc())
    result = await db.execute(stmt)
    alerts = list(result.scalars().all())

    # Fetch news for briefing
    news_items = []
    try:
        from app.news.service import get_news_for_briefing
        news_items = await get_news_for_briefing(db, user_id, limit=3)
    except Exception as e:
        logger.error(f"Failed to get news for briefing: {e}")

    return {
        "date": today.strftime("%Y-%m-%d"),
        "alert_count": len(alerts),
        "alerts": [
            {
                "id": str(a.id),
                "type": a.alert_type.value,
                "title": a.title,
                "message": a.message,
                "is_read": a.is_read,
                "data": json.loads(a.data_json) if a.data_json else None,
            }
            for a in alerts
        ],
        "news": news_items,
    }
