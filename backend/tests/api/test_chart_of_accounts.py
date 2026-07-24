"""Tests for the Chart of Accounts (Phase 1.1).

Covers the double-entry spine: normal-balance derivation, tenant-scoped seeding +
migration of the flat cashbook, CRUD, code-uniqueness, and — the non-negotiable —
cross-tenant isolation.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import coa_service
from app.accounting.coa_schemas import ChartAccountCreate, ChartAccountUpdate
from app.accounting.ledger_models import NORMAL_BALANCE, AccountType, ChartAccount
from app.auth.models import User
from app.cashbook.models import (
    AccountType as PayAccountType,
    CategoryType,
    PaymentAccount,
    TransactionCategory,
)
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Normal-balance derivation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_normal_balance_map():
    assert NORMAL_BALANCE[AccountType.ASSET] == "debit"
    assert NORMAL_BALANCE[AccountType.EXPENSE] == "debit"
    assert NORMAL_BALANCE[AccountType.LIABILITY] == "credit"
    assert NORMAL_BALANCE[AccountType.EQUITY] == "credit"
    assert NORMAL_BALANCE[AccountType.INCOME] == "credit"
    # Every type is mapped — a missing entry would KeyError at report time.
    assert set(NORMAL_BALANCE) == set(AccountType)


async def test_chart_account_normal_balance_property(db: AsyncSession, admin_user: User):
    acct = ChartAccount(
        user_id=admin_user.id, code="9999", name="Probe", account_type=AccountType.INCOME
    )
    assert acct.normal_balance == "credit"


# ---------------------------------------------------------------------------
# Seeding + migration
# ---------------------------------------------------------------------------


async def test_seed_creates_standard_chart(db: AsyncSession, admin_user: User):
    result = await coa_service.seed_default_coa(db, admin_user, migrate=False)
    assert result.accounts_created == len(coa_service.DEFAULT_COA)
    assert result.already_seeded is False

    accounts = await coa_service.list_accounts(db, admin_user)
    codes = {a.code for a in accounts}
    assert coa_service.CODE_ACCOUNTS_PAYABLE in codes
    assert coa_service.CODE_OTHER_INCOME in codes
    # Well-known accounts are is_system so they survive customisation.
    ap = next(a for a in accounts if a.code == coa_service.CODE_ACCOUNTS_PAYABLE)
    assert ap.is_system is True
    assert ap.account_type == AccountType.LIABILITY


async def test_seed_is_idempotent(db: AsyncSession, admin_user: User):
    await coa_service.seed_default_coa(db, admin_user, migrate=False)
    second = await coa_service.seed_default_coa(db, admin_user, migrate=False)
    assert second.accounts_created == 0
    assert second.already_seeded is True

    accounts = await coa_service.list_accounts(db, admin_user)
    # No duplicates: still exactly the standard chart.
    assert len(accounts) == len(coa_service.DEFAULT_COA)


async def test_seed_migrates_payment_account(
    db: AsyncSession, admin_user: User, sample_payment_account: PaymentAccount
):
    assert sample_payment_account.coa_account_id is None
    result = await coa_service.seed_default_coa(db, admin_user, migrate=True)
    assert result.payment_accounts_mapped == 1

    await db.refresh(sample_payment_account)
    assert sample_payment_account.coa_account_id is not None
    coa = await coa_service.get_account(db, sample_payment_account.coa_account_id, admin_user)
    assert coa.account_type == AccountType.ASSET


async def test_seed_migrates_owned_category(db: AsyncSession, admin_user: User):
    cat = TransactionCategory(
        id=uuid.uuid4(),
        name="Consulting Fees",
        category_type=CategoryType.INCOME,
        created_by=admin_user.id,
    )
    db.add(cat)
    await db.commit()

    result = await coa_service.seed_default_coa(db, admin_user, migrate=True)
    assert result.categories_mapped >= 1

    await db.refresh(cat)
    assert cat.coa_account_id is not None
    coa = await coa_service.get_account(db, cat.coa_account_id, admin_user)
    assert coa.account_type == AccountType.INCOME


async def test_seed_does_not_map_foreign_category(
    db: AsyncSession, accountant_user: User, team_member_user: User
):
    """A category owned by someone else is never stamped with the acting tenant's
    CoA account — that would leak one book into another's report."""
    foreign_cat = TransactionCategory(
        id=uuid.uuid4(),
        name="Someone Elses Category",
        category_type=CategoryType.EXPENSE,
        created_by=team_member_user.id,
    )
    db.add(foreign_cat)
    await db.commit()

    # accountant_user (non-admin) seeds their own CoA.
    await coa_service.seed_default_coa(db, accountant_user, migrate=True)
    await db.refresh(foreign_cat)
    assert foreign_cat.coa_account_id is None


# ---------------------------------------------------------------------------
# CRUD via the API
# ---------------------------------------------------------------------------


async def test_create_and_list_account(client: AsyncClient, admin_user: User):
    resp = await client.post(
        "/api/accounting/accounts",
        headers=auth_header(admin_user),
        json={"code": "7000", "name": "R&D Expense", "account_type": "expense"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["code"] == "7000"
    assert body["normal_balance"] == "debit"
    assert body["is_system"] is False

    resp = await client.get("/api/accounting/accounts", headers=auth_header(admin_user))
    assert resp.status_code == 200
    codes = [a["code"] for a in resp.json()["data"]]
    assert "7000" in codes


async def test_duplicate_code_conflicts(client: AsyncClient, admin_user: User):
    payload = {"code": "7100", "name": "First", "account_type": "expense"}
    r1 = await client.post("/api/accounting/accounts", headers=auth_header(admin_user), json=payload)
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/accounting/accounts",
        headers=auth_header(admin_user),
        json={"code": "7100", "name": "Second", "account_type": "expense"},
    )
    assert r2.status_code == 409, r2.text


async def test_update_account(client: AsyncClient, admin_user: User):
    r = await client.post(
        "/api/accounting/accounts",
        headers=auth_header(admin_user),
        json={"code": "7200", "name": "Old Name", "account_type": "expense"},
    )
    account_id = r.json()["data"]["id"]
    r = await client.patch(
        f"/api/accounting/accounts/{account_id}",
        headers=auth_header(admin_user),
        json={"name": "New Name", "description": "updated"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "New Name"


async def test_deactivate_hides_from_default_list(client: AsyncClient, admin_user: User):
    r = await client.post(
        "/api/accounting/accounts",
        headers=auth_header(admin_user),
        json={"code": "7300", "name": "Temp", "account_type": "asset"},
    )
    account_id = r.json()["data"]["id"]
    r = await client.delete(
        f"/api/accounting/accounts/{account_id}", headers=auth_header(admin_user)
    )
    assert r.status_code == 200
    assert r.json()["data"]["is_active"] is False

    r = await client.get("/api/accounting/accounts", headers=auth_header(admin_user))
    assert account_id not in [a["id"] for a in r.json()["data"]]
    r = await client.get(
        "/api/accounting/accounts?include_inactive=true", headers=auth_header(admin_user)
    )
    assert account_id in [a["id"] for a in r.json()["data"]]


async def test_seed_endpoint(client: AsyncClient, admin_user: User):
    r = await client.post("/api/accounting/accounts/seed", headers=auth_header(admin_user))
    assert r.status_code == 201, r.text
    assert r.json()["data"]["accounts_created"] == len(coa_service.DEFAULT_COA)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_system_account_code_immutable(db: AsyncSession, admin_user: User):
    await coa_service.seed_default_coa(db, admin_user, migrate=False)
    ap = next(
        a for a in await coa_service.list_accounts(db, admin_user)
        if a.code == coa_service.CODE_ACCOUNTS_PAYABLE
    )
    with pytest.raises(Exception) as exc:
        await coa_service.update_account(
            db, ap.id, ChartAccountUpdate(code="2001"), admin_user
        )
    assert "system account" in str(exc.value).lower()


async def test_account_cannot_be_own_parent(db: AsyncSession, admin_user: User):
    acct = await coa_service.create_account(
        db, ChartAccountCreate(code="7400", name="Node", account_type=AccountType.ASSET), admin_user
    )
    with pytest.raises(Exception) as exc:
        await coa_service.update_account(
            db, acct.id, ChartAccountUpdate(parent_id=acct.id), admin_user
        )
    assert "own parent" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Cross-tenant isolation — the load-bearing guarantee
# ---------------------------------------------------------------------------


async def test_tenant_cannot_see_others_accounts(
    client: AsyncClient, accountant_user: User, team_member_user: User
):
    r = await client.post(
        "/api/accounting/accounts",
        headers=auth_header(accountant_user),
        json={"code": "8000", "name": "Private", "account_type": "asset"},
    )
    assert r.status_code == 201
    account_id = r.json()["data"]["id"]

    # A different, non-admin tenant sees nothing of it.
    r = await client.get("/api/accounting/accounts", headers=auth_header(team_member_user))
    assert account_id not in [a["id"] for a in r.json()["data"]]

    r = await client.get(
        f"/api/accounting/accounts/{account_id}", headers=auth_header(team_member_user)
    )
    assert r.status_code == 404  # 404 not 403 — never leak existence

    r = await client.patch(
        f"/api/accounting/accounts/{account_id}",
        headers=auth_header(team_member_user),
        json={"name": "Hijacked"},
    )
    assert r.status_code == 404


async def test_two_tenants_may_share_a_code(
    client: AsyncClient, accountant_user: User, team_member_user: User
):
    """Codes are unique PER TENANT, not globally — both may have a '4000'."""
    p = {"code": "4000", "name": "Sales", "account_type": "income"}
    r1 = await client.post("/api/accounting/accounts", headers=auth_header(accountant_user), json=p)
    r2 = await client.post("/api/accounting/accounts", headers=auth_header(team_member_user), json=p)
    assert r1.status_code == 201
    assert r2.status_code == 201
