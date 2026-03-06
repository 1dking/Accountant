"""Business logic for the reconciliation module."""

import difflib
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense
from app.auth.models import User
from app.cashbook.models import CashbookEntry
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.reconciliation.models import MatchStatus, ReceiptTransactionMatch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Matching algorithm helpers
# ---------------------------------------------------------------------------


def _compute_amount_score(expense_amount: float, entry_amount: float) -> float:
    """Score 0-100 based on how close the amounts are.

    100 if exact match, scaling linearly down to 50 at 10% deviation.
    """
    if expense_amount == 0 and entry_amount == 0:
        return 100.0
    denominator = max(abs(expense_amount), 0.01)
    deviation = abs(expense_amount - entry_amount) / denominator
    if deviation > 0.10:
        return 0.0
    # 100 at 0% deviation, 50 at 10% deviation
    return 100.0 - (deviation / 0.10) * 50.0


def _compute_date_score(expense_date: date, entry_date: date) -> float:
    """Score 0-100 based on how close the dates are.

    100 if same day, 90 if 1 day, 70 if 3 days, 50 at 7 days.
    """
    day_diff = abs((expense_date - entry_date).days)
    if day_diff > 7:
        return 0.0
    if day_diff == 0:
        return 100.0
    if day_diff == 1:
        return 90.0
    if day_diff <= 3:
        return 70.0
    # 4-7 days: linearly from ~60 to 50
    return 50.0 + (7 - day_diff) / 4.0 * 10.0


def _compute_vendor_score(vendor: str | None, description: str | None) -> float:
    """Score 0-100 based on fuzzy match between vendor name and description."""
    if not vendor or not description:
        return 0.0
    vendor_lower = vendor.lower().strip()
    desc_lower = description.lower().strip()

    # Substring match bonus
    if vendor_lower in desc_lower or desc_lower in vendor_lower:
        return 90.0

    ratio = difflib.SequenceMatcher(None, vendor_lower, desc_lower).ratio()
    return ratio * 100.0


def _amounts_within_threshold(expense_amount: float, entry_amount: float) -> bool:
    """Check if amounts are within 10% of each other."""
    denominator = max(abs(expense_amount), 0.01)
    return abs(expense_amount - entry_amount) / denominator <= 0.10


def _dates_within_threshold(expense_date: date, entry_date: date) -> bool:
    """Check if dates are within 7 days of each other."""
    return abs((expense_date - entry_date).days) <= 7


def _vendor_matches(vendor: str | None, description: str | None) -> bool:
    """Check if vendor and description have a fuzzy match above threshold."""
    if not vendor or not description:
        # If no vendor, we can still match on amount/date alone
        return True
    vendor_lower = vendor.lower().strip()
    desc_lower = description.lower().strip()

    # Substring match
    if vendor_lower in desc_lower or desc_lower in vendor_lower:
        return True

    ratio = difflib.SequenceMatcher(None, vendor_lower, desc_lower).ratio()
    return ratio > 0.4


def _build_match_reason(
    amount_score: float,
    date_score: float,
    vendor_score: float,
    confidence: float,
) -> str:
    """Build a human-readable explanation for the match."""
    parts = []
    if amount_score >= 90:
        parts.append("exact amount match")
    elif amount_score >= 50:
        parts.append("close amount")

    if date_score >= 90:
        parts.append("same/next day")
    elif date_score >= 70:
        parts.append("within 3 days")
    elif date_score >= 50:
        parts.append("within a week")

    if vendor_score >= 80:
        parts.append("strong vendor match")
    elif vendor_score >= 40:
        parts.append("partial vendor match")

    reason = "; ".join(parts) if parts else "algorithmic match"
    return f"{reason} (confidence: {confidence:.0f}%)"


# ---------------------------------------------------------------------------
# Core matching: find_matches
# ---------------------------------------------------------------------------


async def find_matches(
    db: AsyncSession,
    user_id: uuid.UUID,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """Run the matching algorithm and create ReceiptTransactionMatch records.

    1. Get unmatched expenses for user
    2. Get unmatched cashbook entries for user
    3. Score each pair on amount, date, vendor
    4. Create PENDING matches for pairs with confidence >= 50
    """
    # -----------------------------------------------------------------------
    # Step 1: Get expenses that don't have a confirmed or pending match
    # -----------------------------------------------------------------------
    matched_receipt_ids_subq = (
        select(ReceiptTransactionMatch.receipt_id)
        .where(
            ReceiptTransactionMatch.status.in_([
                MatchStatus.PENDING,
                MatchStatus.CONFIRMED,
            ])
        )
        .correlate(None)
    )

    expense_query = select(Expense).where(
        Expense.user_id == user_id,
        Expense.id.notin_(matched_receipt_ids_subq),
    )

    if date_from:
        try:
            expense_query = expense_query.where(
                Expense.date >= date.fromisoformat(date_from)
            )
        except ValueError:
            pass
    if date_to:
        try:
            expense_query = expense_query.where(
                Expense.date <= date.fromisoformat(date_to)
            )
        except ValueError:
            pass

    expense_result = await db.execute(expense_query)
    expenses = list(expense_result.scalars().all())

    if not expenses:
        return []

    # -----------------------------------------------------------------------
    # Step 2: Get cashbook entries that don't have a confirmed or pending match
    # -----------------------------------------------------------------------
    matched_txn_ids_subq = (
        select(ReceiptTransactionMatch.transaction_id)
        .where(
            ReceiptTransactionMatch.status.in_([
                MatchStatus.PENDING,
                MatchStatus.CONFIRMED,
            ])
        )
        .correlate(None)
    )

    entry_query = select(CashbookEntry).where(
        CashbookEntry.user_id == user_id,
        CashbookEntry.id.notin_(matched_txn_ids_subq),
    )

    if date_from:
        try:
            entry_query = entry_query.where(
                CashbookEntry.date >= date.fromisoformat(date_from)
            )
        except ValueError:
            pass
    if date_to:
        try:
            entry_query = entry_query.where(
                CashbookEntry.date <= date.fromisoformat(date_to)
            )
        except ValueError:
            pass

    entry_result = await db.execute(entry_query)
    entries = list(entry_result.scalars().all())

    if not entries:
        return []

    # -----------------------------------------------------------------------
    # Step 3: Score each pair and build matches
    # -----------------------------------------------------------------------
    created_matches: list[dict] = []
    # Track which entries have been matched to avoid duplicate matches
    matched_entry_ids: set[uuid.UUID] = set()

    for expense in expenses:
        best_match: dict | None = None
        best_confidence: float = 0.0

        expense_amount = float(expense.amount)
        expense_date = expense.date
        expense_vendor = expense.vendor_name

        for entry in entries:
            if entry.id in matched_entry_ids:
                continue

            entry_amount = float(entry.total_amount)
            entry_date = entry.date
            entry_desc = entry.description

            # Pre-filter: must pass amount + date thresholds
            if not _amounts_within_threshold(expense_amount, entry_amount):
                continue
            if not _dates_within_threshold(expense_date, entry_date):
                continue
            if not _vendor_matches(expense_vendor, entry_desc):
                continue

            # Compute scores
            amount_score = _compute_amount_score(expense_amount, entry_amount)
            date_score = _compute_date_score(expense_date, entry_date)
            vendor_score = _compute_vendor_score(expense_vendor, entry_desc)

            # Weighted confidence
            confidence = (
                amount_score * 0.4
                + date_score * 0.3
                + vendor_score * 0.3
            )

            if confidence >= 50 and confidence > best_confidence:
                best_confidence = confidence
                best_match = {
                    "entry": entry,
                    "confidence": round(confidence, 2),
                    "amount_score": amount_score,
                    "date_score": date_score,
                    "vendor_score": vendor_score,
                }

        if best_match is not None:
            entry = best_match["entry"]
            matched_entry_ids.add(entry.id)

            match_reason = _build_match_reason(
                best_match["amount_score"],
                best_match["date_score"],
                best_match["vendor_score"],
                best_match["confidence"],
            )

            match_record = ReceiptTransactionMatch(
                id=uuid.uuid4(),
                receipt_id=expense.id,
                transaction_id=entry.id,
                match_confidence=best_match["confidence"],
                match_reason=match_reason,
                status=MatchStatus.PENDING,
            )
            db.add(match_record)

            created_matches.append({
                "match_record": match_record,
                "receipt_vendor": expense.vendor_name,
                "receipt_amount": float(expense.amount),
                "receipt_date": str(expense.date),
                "transaction_description": entry.description,
                "transaction_amount": float(entry.total_amount),
                "transaction_date": str(entry.date),
            })

    if not created_matches:
        return []

    await db.commit()

    # Build response dicts after commit so all fields are populated
    result = []
    for item in created_matches:
        m = item["match_record"]
        await db.refresh(m)
        result.append({
            "id": m.id,
            "receipt_id": m.receipt_id,
            "transaction_id": m.transaction_id,
            "match_confidence": float(m.match_confidence),
            "match_reason": m.match_reason,
            "status": m.status.value if hasattr(m.status, "value") else m.status,
            "confirmed_by": m.confirmed_by,
            "confirmed_at": m.confirmed_at,
            "receipt_vendor": item["receipt_vendor"],
            "receipt_amount": item["receipt_amount"],
            "receipt_date": item["receipt_date"],
            "transaction_description": item["transaction_description"],
            "transaction_amount": item["transaction_amount"],
            "transaction_date": item["transaction_date"],
            "created_at": m.created_at,
            "updated_at": m.updated_at,
        })

    return result


# ---------------------------------------------------------------------------
# Confirm / Reject / Manual Match
# ---------------------------------------------------------------------------


async def confirm_match(
    db: AsyncSession,
    match_id: uuid.UUID,
    user: User,
) -> ReceiptTransactionMatch:
    """Confirm a pending match."""
    result = await db.execute(
        select(ReceiptTransactionMatch).where(
            ReceiptTransactionMatch.id == match_id
        )
    )
    match_record = result.scalar_one_or_none()
    if match_record is None:
        raise NotFoundError("Match", str(match_id))

    match_record.status = MatchStatus.CONFIRMED
    match_record.confirmed_by = user.id
    match_record.confirmed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(match_record)
    return match_record


async def reject_match(
    db: AsyncSession,
    match_id: uuid.UUID,
    user: User,
) -> ReceiptTransactionMatch:
    """Reject a pending match."""
    result = await db.execute(
        select(ReceiptTransactionMatch).where(
            ReceiptTransactionMatch.id == match_id
        )
    )
    match_record = result.scalar_one_or_none()
    if match_record is None:
        raise NotFoundError("Match", str(match_id))

    match_record.status = MatchStatus.REJECTED
    match_record.confirmed_by = user.id
    match_record.confirmed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(match_record)
    return match_record


async def create_manual_match(
    db: AsyncSession,
    receipt_id: uuid.UUID,
    transaction_id: uuid.UUID,
    user: User,
) -> ReceiptTransactionMatch:
    """Create a manual match between a receipt and transaction (100% confidence)."""
    # Validate receipt exists
    receipt_result = await db.execute(
        select(Expense).where(Expense.id == receipt_id)
    )
    if receipt_result.scalar_one_or_none() is None:
        raise NotFoundError("Expense", str(receipt_id))

    # Validate transaction exists
    txn_result = await db.execute(
        select(CashbookEntry).where(CashbookEntry.id == transaction_id)
    )
    if txn_result.scalar_one_or_none() is None:
        raise NotFoundError("CashbookEntry", str(transaction_id))

    match_record = ReceiptTransactionMatch(
        receipt_id=receipt_id,
        transaction_id=transaction_id,
        match_confidence=100.0,
        match_reason="Manual match by user",
        status=MatchStatus.CONFIRMED,
        confirmed_by=user.id,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(match_record)
    await db.commit()
    await db.refresh(match_record)
    return match_record


# ---------------------------------------------------------------------------
# Listing / Querying
# ---------------------------------------------------------------------------


async def list_matches(
    db: AsyncSession,
    user_id: uuid.UUID,
    status: MatchStatus | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """List matches with joined receipt and transaction details.

    Returns (list_of_match_dicts, total_count).
    """
    query = (
        select(
            ReceiptTransactionMatch,
            Expense.vendor_name.label("receipt_vendor"),
            Expense.amount.label("receipt_amount"),
            Expense.date.label("receipt_date"),
            CashbookEntry.description.label("transaction_description"),
            CashbookEntry.total_amount.label("transaction_amount"),
            CashbookEntry.date.label("transaction_date"),
        )
        .join(Expense, ReceiptTransactionMatch.receipt_id == Expense.id)
        .join(CashbookEntry, ReceiptTransactionMatch.transaction_id == CashbookEntry.id)
        .where(Expense.user_id == user_id)
    )

    if status is not None:
        query = query.where(ReceiptTransactionMatch.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(ReceiptTransactionMatch.created_at.desc())
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    matches = []
    for row in rows:
        match_record = row[0]
        matches.append({
            "id": match_record.id,
            "receipt_id": match_record.receipt_id,
            "transaction_id": match_record.transaction_id,
            "match_confidence": float(match_record.match_confidence),
            "match_reason": match_record.match_reason,
            "status": match_record.status.value if hasattr(match_record.status, "value") else match_record.status,
            "confirmed_by": match_record.confirmed_by,
            "confirmed_at": match_record.confirmed_at,
            "receipt_vendor": row.receipt_vendor,
            "receipt_amount": float(row.receipt_amount) if row.receipt_amount else 0.0,
            "receipt_date": str(row.receipt_date) if row.receipt_date else "",
            "transaction_description": row.transaction_description or "",
            "transaction_amount": float(row.transaction_amount) if row.transaction_amount else 0.0,
            "transaction_date": str(row.transaction_date) if row.transaction_date else "",
            "created_at": match_record.created_at,
            "updated_at": match_record.updated_at,
        })

    return matches, total_count


# ---------------------------------------------------------------------------
# Unmatched receipts / transactions
# ---------------------------------------------------------------------------


async def get_unmatched_receipts(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Expense], int]:
    """Get expenses that have no confirmed or pending matches."""
    # Subquery: receipt IDs that have a non-rejected match
    active_match_receipt_ids = (
        select(ReceiptTransactionMatch.receipt_id)
        .where(
            ReceiptTransactionMatch.status.in_([
                MatchStatus.PENDING,
                MatchStatus.CONFIRMED,
            ])
        )
        .correlate(None)
    )

    query = select(Expense).where(
        Expense.user_id == user_id,
        Expense.id.notin_(active_match_receipt_ids),
    )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(Expense.date.desc(), Expense.created_at.desc())
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    expenses = list(result.scalars().all())

    return expenses, total_count


async def get_unmatched_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[CashbookEntry], int]:
    """Get cashbook entries that have no confirmed or pending matches."""
    # Subquery: transaction IDs that have a non-rejected match
    active_match_txn_ids = (
        select(ReceiptTransactionMatch.transaction_id)
        .where(
            ReceiptTransactionMatch.status.in_([
                MatchStatus.PENDING,
                MatchStatus.CONFIRMED,
            ])
        )
        .correlate(None)
    )

    query = select(CashbookEntry).where(
        CashbookEntry.user_id == user_id,
        CashbookEntry.id.notin_(active_match_txn_ids),
    )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(CashbookEntry.date.desc(), CashbookEntry.created_at.desc())
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    entries = list(result.scalars().all())

    return entries, total_count


# ---------------------------------------------------------------------------
# Reconciliation summary
# ---------------------------------------------------------------------------


async def get_reconciliation_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """Compute high-level reconciliation statistics for the user."""
    # Pending matches count
    pending_count = await db.scalar(
        select(func.count())
        .select_from(ReceiptTransactionMatch)
        .join(Expense, ReceiptTransactionMatch.receipt_id == Expense.id)
        .where(
            Expense.user_id == user_id,
            ReceiptTransactionMatch.status == MatchStatus.PENDING,
        )
    ) or 0

    # Confirmed matches count
    confirmed_count = await db.scalar(
        select(func.count())
        .select_from(ReceiptTransactionMatch)
        .join(Expense, ReceiptTransactionMatch.receipt_id == Expense.id)
        .where(
            Expense.user_id == user_id,
            ReceiptTransactionMatch.status == MatchStatus.CONFIRMED,
        )
    ) or 0

    # Total matched amount (sum of confirmed match receipt amounts)
    total_matched_amount = await db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0.0))
        .select_from(ReceiptTransactionMatch)
        .join(Expense, ReceiptTransactionMatch.receipt_id == Expense.id)
        .where(
            Expense.user_id == user_id,
            ReceiptTransactionMatch.status == MatchStatus.CONFIRMED,
        )
    ) or 0

    # Unmatched receipts count
    active_match_receipt_ids = (
        select(ReceiptTransactionMatch.receipt_id)
        .where(
            ReceiptTransactionMatch.status.in_([
                MatchStatus.PENDING,
                MatchStatus.CONFIRMED,
            ])
        )
        .correlate(None)
    )
    unmatched_receipts_count = await db.scalar(
        select(func.count()).where(
            Expense.user_id == user_id,
            Expense.id.notin_(active_match_receipt_ids),
        )
    ) or 0

    # Unmatched transactions count
    active_match_txn_ids = (
        select(ReceiptTransactionMatch.transaction_id)
        .where(
            ReceiptTransactionMatch.status.in_([
                MatchStatus.PENDING,
                MatchStatus.CONFIRMED,
            ])
        )
        .correlate(None)
    )
    unmatched_transactions_count = await db.scalar(
        select(func.count()).where(
            CashbookEntry.user_id == user_id,
            CashbookEntry.id.notin_(active_match_txn_ids),
        )
    ) or 0

    return {
        "pending_matches": pending_count,
        "confirmed_matches": confirmed_count,
        "unmatched_receipts": unmatched_receipts_count,
        "unmatched_transactions": unmatched_transactions_count,
        "total_matched_amount": float(total_matched_amount),
    }
