"""Tests for Accounts Payable / vendor bills (Phase 1.4).

The bill lifecycle and — critically — its ledger effects: approval posts
Dr expense / Cr AP, payment posts Dr AP / Cr cash, and the Trial Balance stays
balanced throughout. Plus approval-queue, period locking, void semantics, and
tenant isolation.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import coa_service, ledger_reports
from app.auth.models import User
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def _accounts(db, user):
    await coa_service.seed_default_coa(db, user, migrate=False)
    return {a.code: a for a in await coa_service.list_accounts(db, user)}


def _bill_payload(expense_id, amount="200.00", status=None, bill_number=None):
    p = {
        "vendor_name": "Acme Supplies",
        "bill_date": date(2026, 4, 1).isoformat(),
        "due_date": date(2026, 5, 1).isoformat(),
        "lines": [{"account_id": str(expense_id), "description": "Widgets", "amount": amount}],
    }
    if status:
        p["status"] = status
    if bill_number:
        p["bill_number"] = bill_number
    return p


async def test_create_bill_totals_lines(client, db, admin_user: User):
    accts = await _accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/bills",
        headers=auth_header(admin_user),
        json={
            "vendor_name": "Acme",
            "bill_date": date(2026, 4, 1).isoformat(),
            "lines": [
                {"account_id": str(accts["6300"].id), "amount": "50.00"},
                {"account_id": str(accts["6600"].id), "amount": "30.00"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["total_amount"] == "80.00"
    assert body["status"] == "draft"
    assert body["bill_number"].startswith("BILL-")


async def test_approve_posts_expense_and_ap(client, db, admin_user: User):
    accts = await _accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/bills", headers=auth_header(admin_user),
        json=_bill_payload(accts["6300"].id, "200.00"),
    )
    bill_id = r.json()["data"]["id"]
    r = await client.post(f"/api/accounting/bills/{bill_id}/approve", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "approved"
    assert r.json()["data"]["approval_journal_id"] is not None

    # Ledger: expense 6300 debited 200, AP 2000 credited 200; TB balances.
    postings = await ledger_reports.gather_postings(db, admin_user)
    tb = ledger_reports.trial_balance(postings)
    assert tb["balanced"] is True
    by_code = {row["code"]: row for row in tb["rows"]}
    assert by_code["6300"]["debit"] == Decimal("200.00")
    assert by_code["2000"]["credit"] == Decimal("200.00")


async def test_pay_moves_ap_to_cash(client, db, admin_user: User):
    accts = await _accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/bills", headers=auth_header(admin_user),
        json=_bill_payload(accts["6300"].id, "200.00"),
    )
    bill_id = r.json()["data"]["id"]
    await client.post(f"/api/accounting/bills/{bill_id}/approve", headers=auth_header(admin_user))
    r = await client.post(
        f"/api/accounting/bills/{bill_id}/pay",
        headers=auth_header(admin_user),
        json={"cash_account_id": str(accts["1000"].id), "payment_date": date(2026, 4, 15).isoformat()},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "paid"
    assert r.json()["data"]["payment_journal_id"] is not None

    # After payment: AP nets to zero, cash is credited 200 (reduced).
    postings = await ledger_reports.gather_postings(db, admin_user)
    tb = ledger_reports.trial_balance(postings)
    assert tb["balanced"] is True
    by_code = {row["code"]: row for row in tb["rows"]}
    # AP fully cleared → not in TB (net zero).
    assert "2000" not in by_code
    # Cash 1000: debit 0 / credit 200 net → credit column 200.
    assert by_code["1000"]["credit"] == Decimal("200.00")


async def test_cannot_pay_unapproved(client, db, admin_user: User):
    accts = await _accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/bills", headers=auth_header(admin_user),
        json=_bill_payload(accts["6300"].id),
    )
    bill_id = r.json()["data"]["id"]
    r = await client.post(
        f"/api/accounting/bills/{bill_id}/pay",
        headers=auth_header(admin_user),
        json={"cash_account_id": str(accts["1000"].id), "payment_date": date(2026, 4, 15).isoformat()},
    )
    assert r.status_code == 422
    assert "approved" in r.text.lower()


async def test_approval_queue_lists_pending(client, db, admin_user: User):
    accts = await _accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/bills", headers=auth_header(admin_user),
        json=_bill_payload(accts["6300"].id, status="pending"),
    )
    bill_id = r.json()["data"]["id"]
    r = await client.get("/api/accounting/bills/approval-queue", headers=auth_header(admin_user))
    assert bill_id in [b["id"] for b in r.json()["data"]]


async def test_approve_into_closed_period_refused(client, db, admin_user: User):
    from app.accounting import period_service

    accts = await _accounts(db, admin_user)
    await period_service.close_period(db, 2026, 4, admin_user)
    r = await client.post(
        "/api/accounting/bills", headers=auth_header(admin_user),
        json=_bill_payload(accts["6300"].id),
    )
    bill_id = r.json()["data"]["id"]
    r = await client.post(f"/api/accounting/bills/{bill_id}/approve", headers=auth_header(admin_user))
    assert r.status_code == 422
    assert "closed" in r.text.lower()


async def test_void_approved_reverses_ap(client, db, admin_user: User):
    accts = await _accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/bills", headers=auth_header(admin_user),
        json=_bill_payload(accts["6300"].id, "200.00"),
    )
    bill_id = r.json()["data"]["id"]
    await client.post(f"/api/accounting/bills/{bill_id}/approve", headers=auth_header(admin_user))
    r = await client.post(f"/api/accounting/bills/{bill_id}/void", headers=auth_header(admin_user))
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "void"
    # The approval journal was voided → nothing left in the ledger.
    postings = await ledger_reports.gather_postings(db, admin_user)
    tb = ledger_reports.trial_balance(postings)
    assert tb["total_debit"] == Decimal("0.00")


async def test_cannot_void_paid(client, db, admin_user: User):
    accts = await _accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/bills", headers=auth_header(admin_user),
        json=_bill_payload(accts["6300"].id),
    )
    bill_id = r.json()["data"]["id"]
    await client.post(f"/api/accounting/bills/{bill_id}/approve", headers=auth_header(admin_user))
    await client.post(
        f"/api/accounting/bills/{bill_id}/pay",
        headers=auth_header(admin_user),
        json={"cash_account_id": str(accts["1000"].id), "payment_date": date(2026, 4, 15).isoformat()},
    )
    r = await client.post(f"/api/accounting/bills/{bill_id}/void", headers=auth_header(admin_user))
    assert r.status_code == 422
    assert "paid" in r.text.lower()


async def test_bills_isolated_by_tenant(
    client, db, accountant_user: User, team_member_user: User
):
    accts = await _accounts(db, accountant_user)
    r = await client.post(
        "/api/accounting/bills", headers=auth_header(accountant_user),
        json=_bill_payload(accts["6300"].id),
    )
    bill_id = r.json()["data"]["id"]
    r = await client.get("/api/accounting/bills", headers=auth_header(team_member_user))
    assert bill_id not in [b["id"] for b in r.json()["data"]]
    r = await client.get(f"/api/accounting/bills/{bill_id}", headers=auth_header(team_member_user))
    assert r.status_code == 404
    # And can't approve someone else's bill.
    r = await client.post(f"/api/accounting/bills/{bill_id}/approve", headers=auth_header(team_member_user))
    assert r.status_code == 404
