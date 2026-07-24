"""Accounts Payable — vendor bills.

The AP counterpart to invoicing (AR). A bill's lifecycle posts to the ledger via
the shared journal engine:

* **approve** → Dr each expense/asset line, Cr Accounts Payable (2000), dated the
  bill date. Records ``approval_journal_id``; status → APPROVED.
* **pay**     → Dr Accounts Payable, Cr the paying cash account, dated the payment
  date. Records ``payment_journal_id`` + ``paid_at``; status → PAID.

Both postings go through ``journal_service.post_journal``, so they inherit the
same period-open / tenant-scoped / balanced guarantees as manual entries, and the
Trial Balance stays balanced by construction.

Bills are never hard-deleted. Voiding an APPROVED bill also voids its approval
journal entry (the AP liability is reversed). A PAID bill can't be voided — reverse
the payment first (out of scope for P1.4; flagged for a later credit/reversal pass).
"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.accounting import journal_service
from app.accounting.ap_schemas import VendorBillCreate, VendorBillUpdate
from app.accounting.coa_service import CODE_ACCOUNTS_PAYABLE
from app.accounting.ledger_models import (
    BillStatus,
    ChartAccount,
    JournalEntry,
    JournalEntryStatus,
    VendorBill,
    VendorBillLine,
)
from app.accounting.period_service import assert_period_open
from app.auth.models import User
from app.core.authorization import apply_cashbook_filter
from app.core.exceptions import ConflictError, NotFoundError, ValidationError


def _org_id_for(user: User) -> uuid.UUID | None:
    if user.cashbook_access == "org" and user.org_id:
        return user.org_id
    return None


class _Line:
    """Duck-typed line for journal_service.post_journal."""

    def __init__(self, account_id, debit, credit, description=None):
        self.account_id = account_id
        self.debit = debit
        self.credit = credit
        self.description = description


async def _account_by_code(db: AsyncSession, user: User, code: str) -> ChartAccount:
    stmt = select(ChartAccount).where(ChartAccount.code == code)
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    acct = (await db.execute(stmt)).scalar_one_or_none()
    if acct is None:
        raise ValidationError(
            f"Account {code} not found. Set up your Chart of Accounts first."
        )
    return acct


async def _validate_line_accounts(db: AsyncSession, user: User, ids: set[uuid.UUID]) -> None:
    stmt = select(ChartAccount.id).where(ChartAccount.id.in_(ids))
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    found = {r[0] for r in await db.execute(stmt)}
    missing = ids - found
    if missing:
        raise NotFoundError("ChartAccount", str(next(iter(missing))))


async def _next_bill_number(db: AsyncSession, user: User) -> str:
    """Fallback auto-number when the user doesn't supply the vendor's bill number."""
    stmt = select(func.count()).select_from(VendorBill)
    stmt = apply_cashbook_filter(stmt, VendorBill.user_id, VendorBill.org_id, user)
    n = (await db.execute(stmt)).scalar() or 0
    return f"BILL-{n + 1:05d}"


async def create_bill(db: AsyncSession, data: VendorBillCreate, user: User) -> VendorBill:
    total = sum((ln.amount for ln in data.lines), Decimal("0"))
    if total <= 0:
        raise ValidationError("A bill total must be positive.")
    await _validate_line_accounts(db, user, {ln.account_id for ln in data.lines})

    bill_number = data.bill_number or await _next_bill_number(db, user)
    # Enforce per-tenant uniqueness explicitly for a friendly error.
    dup = select(VendorBill.id).where(VendorBill.bill_number == bill_number)
    dup = apply_cashbook_filter(dup, VendorBill.user_id, VendorBill.org_id, user)
    if (await db.execute(dup)).first() is not None:
        raise ConflictError(f"Bill number {bill_number} already exists.")

    bill = VendorBill(
        user_id=user.id,
        org_id=_org_id_for(user),
        bill_number=bill_number,
        vendor_contact_id=data.vendor_contact_id,
        vendor_name=data.vendor_name,
        bill_date=data.bill_date,
        due_date=data.due_date,
        memo=data.memo,
        total_amount=total,
        status=BillStatus(data.status) if data.status else BillStatus.DRAFT,
        created_by=user.id,
    )
    for ln in data.lines:
        bill.lines.append(
            VendorBillLine(account_id=ln.account_id, description=ln.description, amount=ln.amount)
        )
    db.add(bill)
    await db.commit()
    return await get_bill(db, bill.id, user)


async def list_bills(
    db: AsyncSession, user: User, *, status: BillStatus | None = None
) -> list[VendorBill]:
    stmt = select(VendorBill).options(selectinload(VendorBill.lines))
    stmt = apply_cashbook_filter(stmt, VendorBill.user_id, VendorBill.org_id, user)
    if status is not None:
        stmt = stmt.where(VendorBill.status == status)
    stmt = stmt.order_by(VendorBill.bill_date.desc(), VendorBill.bill_number.desc())
    return list((await db.execute(stmt)).scalars().unique().all())


async def get_bill(db: AsyncSession, bill_id: uuid.UUID, user: User) -> VendorBill:
    stmt = (
        select(VendorBill)
        .options(selectinload(VendorBill.lines))
        .where(VendorBill.id == bill_id)
    )
    stmt = apply_cashbook_filter(stmt, VendorBill.user_id, VendorBill.org_id, user)
    bill = (await db.execute(stmt)).scalar_one_or_none()
    if bill is None:
        raise NotFoundError("VendorBill", str(bill_id))
    return bill


async def update_bill(
    db: AsyncSession, bill_id: uuid.UUID, data: VendorBillUpdate, user: User
) -> VendorBill:
    bill = await get_bill(db, bill_id, user)
    if bill.status not in (BillStatus.DRAFT, BillStatus.PENDING):
        raise ValidationError("Only a draft or pending bill can be edited.")

    if data.vendor_name is not None:
        bill.vendor_name = data.vendor_name
    if data.vendor_contact_id is not None:
        bill.vendor_contact_id = data.vendor_contact_id
    if data.bill_date is not None:
        bill.bill_date = data.bill_date
    if data.due_date is not None:
        bill.due_date = data.due_date
    if data.memo is not None:
        bill.memo = data.memo
    if data.status is not None:
        bill.status = BillStatus(data.status)

    if data.lines is not None:
        await _validate_line_accounts(db, user, {ln.account_id for ln in data.lines})
        bill.lines.clear()
        for ln in data.lines:
            bill.lines.append(
                VendorBillLine(account_id=ln.account_id, description=ln.description, amount=ln.amount)
            )
        bill.total_amount = sum((ln.amount for ln in data.lines), Decimal("0"))
        if bill.total_amount <= 0:
            raise ValidationError("A bill total must be positive.")

    await db.commit()
    return await get_bill(db, bill_id, user)


async def approve_bill(db: AsyncSession, bill_id: uuid.UUID, user: User) -> VendorBill:
    bill = await get_bill(db, bill_id, user)
    if bill.status not in (BillStatus.DRAFT, BillStatus.PENDING):
        raise ValidationError(f"A {bill.status.value} bill cannot be approved.")
    if not bill.lines:
        raise ValidationError("Cannot approve a bill with no lines.")
    await assert_period_open(db, bill.bill_date)

    ap = await _account_by_code(db, user, CODE_ACCOUNTS_PAYABLE)
    lines = [
        _Line(ln.account_id, Decimal(str(ln.amount)), Decimal("0"), ln.description)
        for ln in bill.lines
    ]
    lines.append(_Line(ap.id, Decimal("0"), Decimal(str(bill.total_amount)), "Accounts Payable"))

    entry = await journal_service.post_journal(
        db, user, date=bill.bill_date, lines=lines,
        memo=f"Bill {bill.bill_number} — {bill.vendor_name}",
        source="bill", source_id=str(bill.id), commit=False,
    )
    bill.status = BillStatus.APPROVED
    bill.approval_journal_id = entry.id
    bill.approved_by = user.id
    await db.commit()
    return await get_bill(db, bill_id, user)


async def pay_bill(
    db: AsyncSession,
    bill_id: uuid.UUID,
    user: User,
    *,
    cash_account_id: uuid.UUID,
    payment_date,
) -> VendorBill:
    bill = await get_bill(db, bill_id, user)
    if bill.status != BillStatus.APPROVED:
        raise ValidationError("Only an approved bill can be paid.")
    await assert_period_open(db, payment_date)

    # cash account must belong to the tenant (validated in post_journal too).
    await _validate_line_accounts(db, user, {cash_account_id})
    ap = await _account_by_code(db, user, CODE_ACCOUNTS_PAYABLE)

    total = Decimal(str(bill.total_amount))
    lines = [
        _Line(ap.id, total, Decimal("0"), "Accounts Payable"),
        _Line(cash_account_id, Decimal("0"), total, f"Payment of {bill.bill_number}"),
    ]
    entry = await journal_service.post_journal(
        db, user, date=payment_date, lines=lines,
        memo=f"Payment of bill {bill.bill_number} — {bill.vendor_name}",
        source="bill", source_id=str(bill.id), commit=False,
    )
    bill.status = BillStatus.PAID
    bill.payment_journal_id = entry.id
    bill.scheduled_payment_date = payment_date
    from datetime import datetime, timezone

    bill.paid_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_bill(db, bill_id, user)


async def void_bill(db: AsyncSession, bill_id: uuid.UUID, user: User) -> VendorBill:
    bill = await get_bill(db, bill_id, user)
    if bill.status == BillStatus.PAID:
        raise ValidationError(
            "A paid bill can't be voided — reverse the payment first."
        )
    if bill.status == BillStatus.VOID:
        raise ValidationError("This bill is already void.")

    # If it was approved, reverse the AP liability by voiding its journal entry.
    if bill.status == BillStatus.APPROVED and bill.approval_journal_id:
        je = await db.get(JournalEntry, bill.approval_journal_id)
        if je is not None and je.status == JournalEntryStatus.POSTED:
            await assert_period_open(db, je.date)
            je.status = JournalEntryStatus.VOID
    bill.status = BillStatus.VOID
    await db.commit()
    return await get_bill(db, bill_id, user)
