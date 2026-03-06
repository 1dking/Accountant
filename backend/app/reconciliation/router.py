"""FastAPI router for the reconciliation module."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.reconciliation import service
from app.reconciliation.models import MatchStatus
from app.reconciliation.schemas import (
    FindMatchesRequest,
    ManualMatchRequest,
    MatchResponse,
    ReconciliationSummary,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Find matches (trigger matching algorithm)
# ---------------------------------------------------------------------------


@router.post("/find-matches")
async def find_matches(
    data: FindMatchesRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Trigger the matching algorithm to find receipt-transaction matches."""
    matches = await service.find_matches(
        db,
        user_id=current_user.id,
        date_from=data.date_from,
        date_to=data.date_to,
    )
    return {
        "data": [MatchResponse(**m) for m in matches],
        "meta": {"total_count": len(matches)},
    }


# ---------------------------------------------------------------------------
# List matches
# ---------------------------------------------------------------------------


@router.get("/matches")
async def list_matches(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(None, description="Filter by match status: pending, confirmed, rejected"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> dict:
    """List all receipt-transaction matches with optional status filter."""
    match_status = None
    if status is not None:
        try:
            match_status = MatchStatus(status)
        except ValueError:
            pass

    matches, total_count = await service.list_matches(
        db,
        user_id=current_user.id,
        status=match_status,
        page=page,
        page_size=page_size,
    )

    import math

    return {
        "data": [MatchResponse(**m) for m in matches],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": math.ceil(total_count / page_size) if total_count > 0 else 0,
        },
    }


# ---------------------------------------------------------------------------
# Confirm / Reject matches
# ---------------------------------------------------------------------------


@router.post("/matches/{match_id}/confirm")
async def confirm_match(
    match_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Confirm a pending match."""
    match_record = await service.confirm_match(db, match_id, current_user)
    return {
        "data": {
            "id": match_record.id,
            "receipt_id": match_record.receipt_id,
            "transaction_id": match_record.transaction_id,
            "match_confidence": float(match_record.match_confidence),
            "match_reason": match_record.match_reason,
            "status": match_record.status.value if hasattr(match_record.status, "value") else match_record.status,
            "confirmed_by": match_record.confirmed_by,
            "confirmed_at": match_record.confirmed_at,
            "created_at": match_record.created_at,
            "updated_at": match_record.updated_at,
        }
    }


@router.post("/matches/{match_id}/reject")
async def reject_match(
    match_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Reject a pending match."""
    match_record = await service.reject_match(db, match_id, current_user)
    return {
        "data": {
            "id": match_record.id,
            "receipt_id": match_record.receipt_id,
            "transaction_id": match_record.transaction_id,
            "match_confidence": float(match_record.match_confidence),
            "match_reason": match_record.match_reason,
            "status": match_record.status.value if hasattr(match_record.status, "value") else match_record.status,
            "confirmed_by": match_record.confirmed_by,
            "confirmed_at": match_record.confirmed_at,
            "created_at": match_record.created_at,
            "updated_at": match_record.updated_at,
        }
    }


# ---------------------------------------------------------------------------
# Manual match
# ---------------------------------------------------------------------------


@router.post("/manual-match", status_code=201)
async def create_manual_match(
    data: ManualMatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create a manual match between a receipt and a transaction."""
    match_record = await service.create_manual_match(
        db,
        receipt_id=data.receipt_id,
        transaction_id=data.transaction_id,
        user=current_user,
    )
    return {
        "data": {
            "id": match_record.id,
            "receipt_id": match_record.receipt_id,
            "transaction_id": match_record.transaction_id,
            "match_confidence": float(match_record.match_confidence),
            "match_reason": match_record.match_reason,
            "status": match_record.status.value if hasattr(match_record.status, "value") else match_record.status,
            "confirmed_by": match_record.confirmed_by,
            "confirmed_at": match_record.confirmed_at,
            "created_at": match_record.created_at,
            "updated_at": match_record.updated_at,
        }
    }


# ---------------------------------------------------------------------------
# Unmatched receipts / transactions
# ---------------------------------------------------------------------------


@router.get("/unmatched-receipts")
async def get_unmatched_receipts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> dict:
    """Get paginated list of expenses with no active match."""
    import math

    expenses, total_count = await service.get_unmatched_receipts(
        db, user_id=current_user.id, page=page, page_size=page_size,
    )
    return {
        "data": [
            {
                "id": e.id,
                "vendor_name": e.vendor_name,
                "description": e.description,
                "amount": float(e.amount),
                "currency": e.currency,
                "date": str(e.date),
                "status": e.status.value if hasattr(e.status, "value") else e.status,
                "created_at": e.created_at,
            }
            for e in expenses
        ],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": math.ceil(total_count / page_size) if total_count > 0 else 0,
        },
    }


@router.get("/unmatched-transactions")
async def get_unmatched_transactions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> dict:
    """Get paginated list of cashbook entries with no active match."""
    import math

    entries, total_count = await service.get_unmatched_transactions(
        db, user_id=current_user.id, page=page, page_size=page_size,
    )
    return {
        "data": [
            {
                "id": e.id,
                "description": e.description,
                "total_amount": float(e.total_amount),
                "entry_type": e.entry_type.value if hasattr(e.entry_type, "value") else e.entry_type,
                "date": str(e.date),
                "account_id": e.account_id,
                "source": e.source,
                "created_at": e.created_at,
            }
            for e in entries
        ],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": math.ceil(total_count / page_size) if total_count > 0 else 0,
        },
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_reconciliation_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get high-level reconciliation statistics."""
    summary = await service.get_reconciliation_summary(db, current_user.id)
    return {"data": ReconciliationSummary(**summary)}
