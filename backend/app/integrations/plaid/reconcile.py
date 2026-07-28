"""Duplicate detection between Plaid-imported transactions and the manual books.

Tax-integrity guard. Connecting a bank must never *silently* double-count a
transaction the user already entered by hand.

Where the risk actually lives (verified in code, 2026-07-27):
  * Plaid sync writes only to `plaid_transactions` with `is_categorized=False`.
    Synced rows are inert — they post to NO ledger. So connecting + syncing
    alone cannot double-count. That review buffer already exists.
  * A Plaid transaction becomes an `Expense`/`Income` only when it is
    *categorized* — manually (service.categorize_transaction) or by a rule
    (categorization_service.apply_rule). Neither path checked for a pre-existing
    manual record, so categorizing a transaction you already typed in by hand
    would create a second copy. THIS module closes that gap.

Behaviour:
  * Manual categorize -> if a likely match exists and the caller did not pass
    `confirm_duplicate`, raise `PossibleDuplicateError` (409) carrying the
    candidates, so the UI flags it for confirmation instead of posting twice.
  * Automatic (rule) categorize -> skip the transaction (leave it uncategorized
    for human review) rather than auto-post a duplicate.

Match = exact amount AND date within `DUP_DATE_WINDOW_DAYS`. Amount is exact
(Plaid stores abs(amount); manual Expense/Income store positive amounts). Date
is windowed because a bank's *posted* date commonly lags the hand-entered date
by a day or two. Deliberately broad: it FLAGS for a human — it never
auto-merges or auto-deletes anything.
"""

from datetime import date as _date
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import AppError

#: A bank's posted date often differs from the hand-entered date by a day or two.
DUP_DATE_WINDOW_DAYS = 4


class PossibleDuplicateError(AppError):
    """409 — a matching manual entry already exists; confirm to post anyway."""

    def __init__(self, candidates: list[dict]):
        n = len(candidates)
        super().__init__(
            code="PLAID_POSSIBLE_DUPLICATE",
            message=(
                f"This looks like {n} transaction(s) you already recorded by hand "
                "(same amount, within a few days). Confirm to add it anyway, or "
                "leave it — it will not be double-counted by accident."
            ),
            status_code=409,
        )
        # Surfaced in the response body by the AppError handler.
        self.details = {"possible_duplicates": candidates}


async def find_duplicate_records(
    db: AsyncSession,
    user: User,
    *,
    amount: Decimal,
    txn_date: _date,
    kind: str,
) -> list[dict]:
    """Existing manual Expense/Income rows that likely match this Plaid txn.

    ``kind`` is the destination ledger for the categorization ("expense" or
    "income") — we only look in the ledger the transaction would post to.
    """
    lo = txn_date - timedelta(days=DUP_DATE_WINDOW_DAYS)
    hi = txn_date + timedelta(days=DUP_DATE_WINDOW_DAYS)

    if kind == "expense":
        from app.accounting.models import Expense

        rows = (
            await db.execute(
                select(Expense).where(
                    Expense.user_id == user.id,
                    Expense.amount == amount,
                    Expense.date >= lo,
                    Expense.date <= hi,
                )
            )
        ).scalars().all()
        return [
            {
                "kind": "expense",
                "id": str(e.id),
                "amount": str(e.amount),
                "date": e.date.isoformat(),
                "description": e.vendor_name or e.description,
            }
            for e in rows
        ]

    if kind == "income":
        from app.income.models import Income

        rows = (
            await db.execute(
                select(Income).where(
                    Income.created_by == user.id,
                    Income.amount == amount,
                    Income.date >= lo,
                    Income.date <= hi,
                )
            )
        ).scalars().all()
        return [
            {
                "kind": "income",
                "id": str(i.id),
                "amount": str(i.amount),
                "date": i.date.isoformat(),
                "description": i.description,
            }
            for i in rows
        ]

    if kind == "cashbook":
        from sqlalchemy import or_ as _or

        from app.cashbook.models import CashbookEntry

        rows = (
            await db.execute(
                select(CashbookEntry).where(
                    CashbookEntry.user_id == user.id,
                    CashbookEntry.total_amount == amount,
                    CashbookEntry.date >= lo,
                    CashbookEntry.date <= hi,
                    CashbookEntry.is_deleted.is_(False),
                    # Exclude our own Plaid-sourced posts: a second bank txn with
                    # the same amount/date is a real separate charge, not a
                    # hand-entered double. Re-posting the SAME txn is stopped by
                    # the idempotency guard (get_entry_by_source), not here.
                    _or(CashbookEntry.source != "plaid", CashbookEntry.source.is_(None)),
                )
            )
        ).scalars().all()
        return [
            {
                "kind": "cashbook",
                "id": str(e.id),
                "amount": str(e.total_amount),
                "date": e.date.isoformat(),
                "description": e.description,
            }
            for e in rows
        ]

    return []
