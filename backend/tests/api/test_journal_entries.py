"""Tests for manual journal entries (Phase 1.2).

Balanced double-entry posting: balance enforcement, per-line one-sidedness,
tenant-scoped account validation, per-tenant entry numbering, period locking,
void semantics, and cross-tenant isolation.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import coa_service
from app.accounting.ledger_models import AccountType, ChartAccount
from app.auth.models import User
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def _two_accounts(db: AsyncSession, user: User) -> tuple[ChartAccount, ChartAccount]:
    """A cash asset and a revenue income account for the tenant."""
    await coa_service.seed_default_coa(db, user, migrate=False)
    accts = {a.code: a for a in await coa_service.list_accounts(db, user)}
    return accts["1000"], accts["4000"]  # Cash on Hand, Sales Revenue


def _entry_payload(cash_id, rev_id, amount="100.00", d=None):
    return {
        "date": (d or date.today()).isoformat(),
        "memo": "Cash sale",
        "lines": [
            {"account_id": str(cash_id), "debit": amount, "credit": "0"},
            {"account_id": str(rev_id), "debit": "0", "credit": amount},
        ],
    }


async def test_create_balanced_entry(client: AsyncClient, db: AsyncSession, admin_user: User):
    cash, rev = await _two_accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/journal",
        headers=auth_header(admin_user),
        json=_entry_payload(cash.id, rev.id),
    )
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["entry_number"] == 1
    assert body["status"] == "posted"
    assert body["total"] == "100.00"
    codes = {ln["account_code"] for ln in body["lines"]}
    assert codes == {"1000", "4000"}


async def test_unbalanced_entry_rejected(client: AsyncClient, db: AsyncSession, admin_user: User):
    cash, rev = await _two_accounts(db, admin_user)
    payload = _entry_payload(cash.id, rev.id)
    payload["lines"][1]["credit"] = "90.00"  # debit 100 ≠ credit 90
    r = await client.post("/api/accounting/journal", headers=auth_header(admin_user), json=payload)
    assert r.status_code == 422, r.text
    assert "balance" in r.text.lower()


async def test_line_cannot_be_both_sides(client: AsyncClient, db: AsyncSession, admin_user: User):
    cash, rev = await _two_accounts(db, admin_user)
    payload = _entry_payload(cash.id, rev.id)
    payload["lines"][0]["credit"] = "5.00"  # debit AND credit on one line
    r = await client.post("/api/accounting/journal", headers=auth_header(admin_user), json=payload)
    assert r.status_code == 422


async def test_zero_entry_rejected(client: AsyncClient, db: AsyncSession, admin_user: User):
    cash, rev = await _two_accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/journal",
        headers=auth_header(admin_user),
        json=_entry_payload(cash.id, rev.id, amount="0.00"),
    )
    assert r.status_code == 422


async def test_entry_numbers_increment_per_tenant(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    cash, rev = await _two_accounts(db, admin_user)
    nums = []
    for _ in range(3):
        r = await client.post(
            "/api/accounting/journal", headers=auth_header(admin_user), json=_entry_payload(cash.id, rev.id)
        )
        nums.append(r.json()["data"]["entry_number"])
    assert nums == [1, 2, 3]


async def test_cannot_post_to_foreign_account(
    client: AsyncClient, db: AsyncSession, accountant_user: User, team_member_user: User
):
    cash, rev = await _two_accounts(db, accountant_user)  # accountant's accounts
    # team_member tries to use accountant's accounts → 404 (never leak existence)
    r = await client.post(
        "/api/accounting/journal",
        headers=auth_header(team_member_user),
        json=_entry_payload(cash.id, rev.id),
    )
    assert r.status_code == 404, r.text


async def test_cannot_post_to_deactivated_account(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    cash, rev = await _two_accounts(db, admin_user)
    await coa_service.deactivate_account(db, rev.id, admin_user)
    r = await client.post(
        "/api/accounting/journal",
        headers=auth_header(admin_user),
        json=_entry_payload(cash.id, rev.id),
    )
    assert r.status_code == 422
    assert "deactivated" in r.text.lower()


async def test_post_into_closed_period_refused(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    from app.accounting import period_service

    cash, rev = await _two_accounts(db, admin_user)
    target = date(2023, 1, 15)
    await period_service.close_period(db, 2023, 1, admin_user)
    r = await client.post(
        "/api/accounting/journal",
        headers=auth_header(admin_user),
        json=_entry_payload(cash.id, rev.id, d=target),
    )
    assert r.status_code == 422
    assert "closed" in r.text.lower()


async def test_void_entry(client: AsyncClient, db: AsyncSession, admin_user: User):
    cash, rev = await _two_accounts(db, admin_user)
    r = await client.post(
        "/api/accounting/journal", headers=auth_header(admin_user), json=_entry_payload(cash.id, rev.id)
    )
    entry_id = r.json()["data"]["id"]
    r = await client.post(f"/api/accounting/journal/{entry_id}/void", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "void"
    # Double-void is refused.
    r = await client.post(f"/api/accounting/journal/{entry_id}/void", headers=auth_header(admin_user))
    assert r.status_code == 422


async def test_list_isolated_by_tenant(
    client: AsyncClient, db: AsyncSession, accountant_user: User, team_member_user: User
):
    cash, rev = await _two_accounts(db, accountant_user)
    r = await client.post(
        "/api/accounting/journal", headers=auth_header(accountant_user), json=_entry_payload(cash.id, rev.id)
    )
    entry_id = r.json()["data"]["id"]

    # team_member sees none of accountant's entries, and can't fetch by id.
    r = await client.get("/api/accounting/journal", headers=auth_header(team_member_user))
    assert entry_id not in [e["id"] for e in r.json()["data"]]
    r = await client.get(f"/api/accounting/journal/{entry_id}", headers=auth_header(team_member_user))
    assert r.status_code == 404
