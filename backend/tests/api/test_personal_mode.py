"""Business/Personal mode — proves the separation the whole feature exists for.

Personal money lives in its own encrypted tables; business reports never query
them; the toggle switches context by header and persists via /auth/me without a
header ever silently overwriting the stored default; and personal data is private
to the individual even in a shared org.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.cashbook.models import (
    AccountType as PAType,
    CashbookEntry,
    EntryType,
    PaymentAccount,
)
from app.core.encryption import init_encryption_service
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _enc():
    # Personal tables use encrypted columns; the request path doesn't run the
    # app lifespan (which would init this), so init a throwaway key per test.
    init_encryption_service(Fernet.generate_key().decode())


def _hdr(user: User, mode: str | None = None) -> dict:
    h = dict(auth_header(user))
    if mode:
        h["X-App-Mode"] = mode
    return h


def _dec(v) -> Decimal:
    return Decimal(str(v))


async def _make_personal_account(client: AsyncClient, user: User, opening="100.00") -> str:
    r = await client.post("/api/personal/accounts", headers=_hdr(user, "personal"), json={
        "name": "My Personal Chequing", "account_type": "bank", "currency": "CAD",
        "opening_balance": opening, "opening_balance_date": "2026-01-01",
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _add_personal_txn(client, user, account_id, direction, amount, desc="x", d="2026-03-02"):
    r = await client.post("/api/personal/transactions", headers=_hdr(user, "personal"), json={
        "account_id": account_id, "date": d, "direction": direction,
        "amount": amount, "description": desc,
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _business_income(db, user, amount="500.00"):
    pa = PaymentAccount(id=uuid.uuid4(), user_id=user.id, name="Biz", account_type=PAType.BANK,
                        opening_balance=Decimal("0"), opening_balance_date=date(2026, 1, 1), is_active=True)
    db.add(pa)
    await db.flush()
    db.add(CashbookEntry(id=uuid.uuid4(), account_id=pa.id, entry_type=EntryType.INCOME,
                         date=date(2026, 3, 1), description="client", total_amount=Decimal(amount), user_id=user.id))
    await db.commit()


async def test_personal_txn_absent_from_business_pl(client, db, admin_user):
    await _business_income(db, admin_user, "500.00")
    acct = await _make_personal_account(client, admin_user)
    await _add_personal_txn(client, admin_user, acct, "in", "999.00", "personal gift")

    r = await client.get("/api/accounting/reports/profit-loss", headers=_hdr(admin_user))  # business mode
    assert r.status_code == 200, r.text
    # Only the $500 business income — the $999 personal transfer is invisible here.
    assert _dec(r.json()["data"]["total_income"]) == Decimal("500.00")


async def test_business_report_403_in_personal_mode(client, admin_user):
    r = await client.get("/api/accounting/reports/profit-loss", headers=_hdr(admin_user, "personal"))
    assert r.status_code == 403
    assert "BUSINESS_MODE_REQUIRED" in r.text


async def test_business_txn_absent_from_personal_cashflow(client, db, admin_user):
    await _business_income(db, admin_user, "500.00")
    acct = await _make_personal_account(client, admin_user)
    await _add_personal_txn(client, admin_user, acct, "in", "999.00")
    await _add_personal_txn(client, admin_user, acct, "out", "50.00")

    r = await client.get("/api/personal/cashflow", headers=_hdr(admin_user, "personal"))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert _dec(data["total_in"]) == Decimal("999.00")   # business $500 NOT here
    assert _dec(data["total_out"]) == Decimal("50.00")
    assert _dec(data["net"]) == Decimal("949.00")


async def test_personal_amount_and_description_encrypted_at_rest(client, db, admin_user):
    acct = await _make_personal_account(client, admin_user)
    await _add_personal_txn(client, admin_user, acct, "out", "42.75", "SECRET MERCHANT")

    row = (await db.execute(text(
        "SELECT amount, description FROM personal_transactions WHERE is_deleted = 0 LIMIT 1"
    ))).first()
    raw_amount, raw_desc = row
    assert str(raw_amount).startswith("gAAAA"), "amount not encrypted at rest"
    assert str(raw_desc).startswith("gAAAA"), "description not encrypted at rest"
    assert "SECRET MERCHANT" not in str(raw_desc)
    # And it round-trips through the API (decrypts correctly).
    r = await client.get("/api/personal/transactions", headers=_hdr(admin_user, "personal"))
    t = r.json()["data"][0]
    assert t["description"] == "SECRET MERCHANT"
    assert _dec(t["amount"]) == Decimal("42.75")


async def test_toggle_persists_via_auth_me(client, admin_user):
    r = await client.get("/api/auth/me", headers=_hdr(admin_user))
    assert r.json()["data"]["active_mode"] == "business"  # default

    r = await client.put("/api/auth/me", headers=_hdr(admin_user), json={"active_mode": "personal"})
    assert r.status_code == 200, r.text

    r = await client.get("/api/auth/me", headers=_hdr(admin_user))  # no header → persisted value
    assert r.json()["data"]["active_mode"] == "personal"


async def test_mode_header_does_not_persist(client, db, admin_user):
    """A request carrying X-App-Mode that COMMITS must NOT overwrite the stored
    default (set_committed_value guard). admin_user defaults to business."""
    acct = await _make_personal_account(client, admin_user)          # header=personal, commits
    await _add_personal_txn(client, admin_user, acct, "out", "5.00")  # header=personal, commits again

    persisted = (await db.execute(
        text("SELECT active_mode FROM users WHERE id = :id"), {"id": admin_user.id.hex}
    )).scalar_one()
    assert persisted == "business", "the X-App-Mode header leaked into the stored default"


async def test_personal_data_is_private_within_an_org(client, db, admin_user):
    """A second user (even an org peer) cannot see another user's personal rows."""
    from app.platform_admin.models import Organization

    org = Organization(id=uuid.uuid4(), name="OrgCo", slug=f"orgco-{uuid.uuid4().hex[:8]}",
                       owner_id=admin_user.id)
    db.add(org)
    await db.flush()
    admin_user.org_id = org.id
    admin_user.cashbook_access = "org"
    peer = User(id=uuid.uuid4(), email="peer@test.com", hashed_password=hash_password("TestPass123!"),
                full_name="Peer", role=Role.ADMIN, is_active=True, org_id=org.id, cashbook_access="org")
    db.add(peer)
    await db.commit()

    await _make_personal_account(client, admin_user)  # admin's personal account

    r = await client.get("/api/personal/accounts", headers=_hdr(peer, "personal"))
    assert r.status_code == 200, r.text
    assert r.json()["data"] == [], "org peer must not see another user's personal accounts"
