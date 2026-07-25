"""Tests for 1099 / contractor tracking (Phase 1.5)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import coa_service, tax1099_service
from app.auth.models import User
from app.contacts.models import Contact, ContactType
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def _vendor(db, user, name="Freelancer LLC", is_1099=True) -> Contact:
    c = Contact(
        id=uuid.uuid4(), type=ContactType.VENDOR, company_name=name,
        contact_name="Pat Contractor", country="US", tax_id="12-3456789",
        is_1099_vendor=is_1099, created_by=user.id,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _paid_bill(db, user, contact, amount, year=2026):
    accts = {a.code: a for a in await coa_service.list_accounts(db, user)}
    from app.accounting.ap_schemas import VendorBillCreate, VendorBillLineInput, VendorBillPay
    from app.accounting import ap_service

    bill = await ap_service.create_bill(
        db,
        VendorBillCreate(
            vendor_name=contact.company_name, vendor_contact_id=contact.id,
            bill_date=date(year, 6, 1),
            lines=[VendorBillLineInput(account_id=accts["6300"].id, amount=Decimal(str(amount)))],
        ),
        user,
    )
    await ap_service.approve_bill(db, bill.id, user)
    await ap_service.pay_bill(
        db, bill.id, user, cash_account_id=accts["1000"].id, payment_date=date(year, 6, 15)
    )
    return bill


async def test_report_totals_paid_1099_vendor(db: AsyncSession, admin_user: User):
    await coa_service.seed_default_coa(db, admin_user, migrate=False)
    vendor = await _vendor(db, admin_user)
    await _paid_bill(db, admin_user, vendor, "1000.00", year=2026)

    report = await tax1099_service.get_1099_report(db, admin_user, 2026)
    assert len(report["vendors"]) == 1
    row = report["vendors"][0]
    assert row["total_paid"] == Decimal("1000.00")
    assert row["meets_threshold"] is True
    assert row["is_1099_vendor"] is True


async def test_report_excludes_other_years(db: AsyncSession, admin_user: User):
    await coa_service.seed_default_coa(db, admin_user, migrate=False)
    vendor = await _vendor(db, admin_user)
    await _paid_bill(db, admin_user, vendor, "1000.00", year=2026)
    report = await tax1099_service.get_1099_report(db, admin_user, 2025)
    assert report["vendors"] == []


async def test_unflagged_over_threshold_is_candidate(db: AsyncSession, admin_user: User):
    await coa_service.seed_default_coa(db, admin_user, migrate=False)
    vendor = await _vendor(db, admin_user, name="Not Flagged Co", is_1099=False)
    await _paid_bill(db, admin_user, vendor, "800.00", year=2026)
    report = await tax1099_service.get_1099_report(db, admin_user, 2026)
    assert report["vendors"] == []
    assert len(report["candidates"]) == 1
    assert report["candidates"][0]["total_paid"] == Decimal("800.00")


async def test_cashbook_expense_counts_toward_total(db: AsyncSession, admin_user: User):
    await coa_service.seed_default_coa(db, admin_user, migrate=False)
    vendor = await _vendor(db, admin_user)
    from app.cashbook.models import CashbookEntry, EntryType

    db.add(
        CashbookEntry(
            id=uuid.uuid4(), entry_type=EntryType.EXPENSE, date=date(2026, 3, 1),
            description="Contract work", total_amount=Decimal("700.00"),
            contact_id=vendor.id, user_id=admin_user.id,
        )
    )
    await db.commit()
    report = await tax1099_service.get_1099_report(db, admin_user, 2026)
    assert report["vendors"][0]["cashbook_total"] == Decimal("700.00")


async def test_set_flag_toggles(client: AsyncClient, db: AsyncSession, admin_user: User):
    vendor = await _vendor(db, admin_user, is_1099=False)
    r = await client.post(
        f"/api/accounting/1099/vendors/{vendor.id}",
        headers=auth_header(admin_user),
        json={"is_1099_vendor": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["is_1099_vendor"] is True


async def test_report_endpoint(client: AsyncClient, db: AsyncSession, admin_user: User):
    await coa_service.seed_default_coa(db, admin_user, migrate=False)
    vendor = await _vendor(db, admin_user)
    await _paid_bill(db, admin_user, vendor, "1200.00", year=2026)
    r = await client.get("/api/accounting/1099/report?year=2026", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["vendors"][0]["total_paid"] == "1200.00"


async def test_report_isolated_by_tenant(
    db: AsyncSession, accountant_user: User, team_member_user: User
):
    await coa_service.seed_default_coa(db, accountant_user, migrate=False)
    vendor = await _vendor(db, accountant_user)
    await _paid_bill(db, accountant_user, vendor, "5000.00", year=2026)
    # team_member's report sees none of accountant's payments.
    report = await tax1099_service.get_1099_report(db, team_member_user, 2026)
    assert report["vendors"] == []
    assert report["candidates"] == []


async def test_set_flag_foreign_contact_404(
    client: AsyncClient, db: AsyncSession, accountant_user: User, team_member_user: User
):
    vendor = await _vendor(db, accountant_user, is_1099=False)
    r = await client.post(
        f"/api/accounting/1099/vendors/{vendor.id}",
        headers=auth_header(team_member_user),
        json={"is_1099_vendor": True},
    )
    assert r.status_code == 404
