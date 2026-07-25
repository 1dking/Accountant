"""1099 / contractor tracking.

A 1099-NEC is owed to any unincorporated contractor a business pays $600+ in a
calendar year. This produces the year-end totals: for a tax year, how much each
contact was paid, from the tenant's own books:

* **paid vendor bills** (status PAID, paid_at in the year), by vendor_contact_id;
* **cashbook expense entries** linked to the contact (contact_id), by date.

Vendors flagged ``is_1099_vendor`` are the reportable set; the report also
surfaces *unflagged* contacts paid over the threshold as candidates, so nobody is
missed at year end. Everything is scoped to the acting tenant — a payment only
counts if it sits in this tenant's bills/cashbook.
"""

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.ledger_models import BillStatus, VendorBill
from app.auth.models import User
from app.cashbook.models import CashbookEntry, EntryType
from app.contacts.models import Contact
from app.core.authorization import apply_cashbook_filter, authorize_owner
from app.core.exceptions import NotFoundError

#: IRS 1099-NEC reporting threshold (USD).
DEFAULT_THRESHOLD = Decimal("600.00")


async def _bill_payments_by_contact(
    db: AsyncSession, user: User, year: int
) -> dict[uuid.UUID, Decimal]:
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    stmt = select(VendorBill).where(
        VendorBill.status == BillStatus.PAID,
        VendorBill.vendor_contact_id.is_not(None),
        VendorBill.paid_at >= start,
        VendorBill.paid_at < end,
    )
    stmt = apply_cashbook_filter(stmt, VendorBill.user_id, VendorBill.org_id, user)
    totals: dict[uuid.UUID, Decimal] = {}
    for bill in (await db.execute(stmt)).scalars().all():
        totals[bill.vendor_contact_id] = totals.get(
            bill.vendor_contact_id, Decimal("0")
        ) + Decimal(str(bill.total_amount))
    return totals


async def _cashbook_payments_by_contact(
    db: AsyncSession, user: User, year: int
) -> dict[uuid.UUID, Decimal]:
    stmt = select(CashbookEntry).where(
        CashbookEntry.entry_type == EntryType.EXPENSE,
        CashbookEntry.contact_id.is_not(None),
        CashbookEntry.is_deleted.is_(False),
        CashbookEntry.split_parent_id.is_(None),
        CashbookEntry.date >= date(year, 1, 1),
        CashbookEntry.date <= date(year, 12, 31),
    )
    stmt = apply_cashbook_filter(stmt, CashbookEntry.user_id, CashbookEntry.org_id, user)
    totals: dict[uuid.UUID, Decimal] = {}
    for e in (await db.execute(stmt)).scalars().all():
        totals[e.contact_id] = totals.get(e.contact_id, Decimal("0")) + Decimal(str(e.total_amount))
    return totals


async def get_1099_report(
    db: AsyncSession,
    user: User,
    year: int,
    *,
    threshold: Decimal = DEFAULT_THRESHOLD,
) -> dict:
    bill_totals = await _bill_payments_by_contact(db, user, year)
    cash_totals = await _cashbook_payments_by_contact(db, user, year)

    contact_ids = set(bill_totals) | set(cash_totals)
    contacts: dict[uuid.UUID, Contact] = {}
    if contact_ids:
        rows = await db.execute(select(Contact).where(Contact.id.in_(contact_ids)))
        contacts = {c.id: c for c in rows.scalars().all()}

    vendors = []
    candidates = []
    for cid in contact_ids:
        c = contacts.get(cid)
        if c is None:
            continue  # contact deleted; skip
        total = bill_totals.get(cid, Decimal("0")) + cash_totals.get(cid, Decimal("0"))
        row = {
            "contact_id": str(cid),
            "name": c.company_name,
            "contact_name": c.contact_name,
            "tax_id": c.tax_id,
            "is_1099_vendor": c.is_1099_vendor,
            "bills_total": bill_totals.get(cid, Decimal("0")),
            "cashbook_total": cash_totals.get(cid, Decimal("0")),
            "total_paid": total,
            "meets_threshold": total >= threshold,
        }
        if c.is_1099_vendor:
            vendors.append(row)
        elif total >= threshold:
            candidates.append(row)

    vendors.sort(key=lambda r: r["total_paid"], reverse=True)
    candidates.sort(key=lambda r: r["total_paid"], reverse=True)
    return {
        "year": year,
        "threshold": threshold,
        "vendors": vendors,
        "candidates": candidates,
    }


async def set_1099_flag(
    db: AsyncSession, user: User, contact_id: uuid.UUID, is_1099_vendor: bool
) -> Contact:
    contact = (
        await db.execute(select(Contact).where(Contact.id == contact_id))
    ).scalar_one_or_none()
    if contact is None:
        raise NotFoundError("Contact", str(contact_id))
    # Toggling tax status is an ownership-level action (creator or admin only).
    authorize_owner(contact.created_by, user, "Contact")
    contact.is_1099_vendor = is_1099_vendor
    await db.commit()
    await db.refresh(contact)
    return contact
