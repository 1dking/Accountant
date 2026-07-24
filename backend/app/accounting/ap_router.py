"""FastAPI router for Accounts Payable / vendor bills."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import ap_service
from app.accounting.ap_schemas import (
    VendorBillCreate,
    VendorBillLineResponse,
    VendorBillPay,
    VendorBillResponse,
    VendorBillUpdate,
)
from app.accounting.ledger_models import BillStatus, VendorBill
from app.auth.models import User
from app.dependencies import get_current_user, get_db

router = APIRouter()


def _to_response(bill: VendorBill) -> VendorBillResponse:
    lines = [
        VendorBillLineResponse(
            id=ln.id,
            account_id=ln.account_id,
            account_code=ln.account.code if ln.account else None,
            account_name=ln.account.name if ln.account else None,
            description=ln.description,
            amount=ln.amount,
        )
        for ln in bill.lines
    ]
    return VendorBillResponse(
        id=bill.id,
        bill_number=bill.bill_number,
        vendor_name=bill.vendor_name,
        vendor_contact_id=bill.vendor_contact_id,
        bill_date=bill.bill_date,
        due_date=bill.due_date,
        memo=bill.memo,
        total_amount=bill.total_amount,
        status=bill.status,
        approval_journal_id=bill.approval_journal_id,
        payment_journal_id=bill.payment_journal_id,
        scheduled_payment_date=bill.scheduled_payment_date,
        paid_at=bill.paid_at,
        created_at=bill.created_at,
        lines=lines,
    )


@router.get("/bills")
async def list_bills(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status: BillStatus | None = None,
) -> dict:
    bills = await ap_service.list_bills(db, user, status=status)
    return {"data": [_to_response(b) for b in bills]}


@router.get("/bills/approval-queue")
async def approval_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Bills awaiting approval (PENDING)."""
    bills = await ap_service.list_bills(db, user, status=BillStatus.PENDING)
    return {"data": [_to_response(b) for b in bills]}


@router.post("/bills", status_code=201)
async def create_bill(
    data: VendorBillCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    bill = await ap_service.create_bill(db, data, user)
    return {"data": _to_response(bill)}


@router.get("/bills/{bill_id}")
async def get_bill(
    bill_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    bill = await ap_service.get_bill(db, bill_id, user)
    return {"data": _to_response(bill)}


@router.patch("/bills/{bill_id}")
async def update_bill(
    bill_id: uuid.UUID,
    data: VendorBillUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    bill = await ap_service.update_bill(db, bill_id, data, user)
    return {"data": _to_response(bill)}


@router.post("/bills/{bill_id}/approve")
async def approve_bill(
    bill_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    bill = await ap_service.approve_bill(db, bill_id, user)
    return {"data": _to_response(bill)}


@router.post("/bills/{bill_id}/pay")
async def pay_bill(
    bill_id: uuid.UUID,
    data: VendorBillPay,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    bill = await ap_service.pay_bill(
        db, bill_id, user, cash_account_id=data.cash_account_id, payment_date=data.payment_date
    )
    return {"data": _to_response(bill)}


@router.post("/bills/{bill_id}/void")
async def void_bill(
    bill_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    bill = await ap_service.void_bill(db, bill_id, user)
    return {"data": _to_response(bill)}
