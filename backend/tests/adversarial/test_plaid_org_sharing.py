"""Org-shared Plaid: two operators see each other's bank feed, but only the
owner can manage a connection; and the Plaid keys config is manager-only.

Pins the shared-workspace contract:
  * An org peer (same org_id + cashbook_access="org") sees another member's
    connections and transactions, and can categorize them.
  * A peer CANNOT disconnect / force-sync another member's bank (owner-only —
    that path decrypts the access token).
  * A user outside the org sees none of it.
  * The Plaid keys config is visible/editable only to the designated manager;
    another operator can still connect but never sees the keys.
"""
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.core.encryption import init_encryption_service
from app.core.exceptions import NotFoundError
from app.integrations.plaid import service
from app.integrations.plaid.models import PlaidConnection, PlaidTransaction
from app.integrations.plaid.schemas import (
    CategorizeTransactionRequest,
    PlaidTransactionFilters,
)

D = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _encryption():
    init_encryption_service(Fernet.generate_key().decode())


async def mk_user(db, email, *, org_id=None, cashbook_access="personal", role=Role.ADMIN) -> User:
    u = User(
        id=uuid.uuid4(), email=email, hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0], role=role, is_active=True,
        org_id=org_id, cashbook_access=cashbook_access,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def mk_org(db, owner) -> uuid.UUID:
    """Create a real organizations row (org_id is a FK, enforced in tests)."""
    from app.platform_admin.models import Organization

    org = Organization(
        id=uuid.uuid4(), name="OCIDM", slug=f"ocidm-{uuid.uuid4().hex[:8]}",
        owner_id=owner.id, is_active=True,
    )
    db.add(org)
    await db.commit()
    return org.id


async def make_org_with_owner(db, email):
    """An owner user + their org, both wired to org cashbook access."""
    owner = await mk_user(db, email)  # created without an org first
    org_id = await mk_org(db, owner)
    owner.org_id = org_id
    owner.cashbook_access = "org"
    await db.commit()
    await db.refresh(owner)
    return owner, org_id


async def mk_connection(db, owner, *, org_id) -> PlaidConnection:
    import json
    conn = PlaidConnection(
        user_id=owner.id, org_id=org_id, institution_name="CIBC", institution_id="ins_1",
        encrypted_access_token="enc", item_id=f"item-{uuid.uuid4().hex[:12]}",
        accounts_json=json.dumps([{"account_id": "acc-1", "name": "Chequing",
                                   "mask": "1234", "iso_currency_code": "CAD"}]),
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def mk_txn(db, conn, *, name="Acme", amount="50.00") -> PlaidTransaction:
    txn = PlaidTransaction(
        plaid_connection_id=conn.id, plaid_transaction_id=f"txn-{uuid.uuid4().hex[:12]}",
        account_id="acc-1", amount=Decimal(amount), date=D,
        name=name, merchant_name=name, is_income=False, is_categorized=False,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


# ---------------------------------------------------------------------------
# Org-shared visibility
# ---------------------------------------------------------------------------


async def test_org_peer_sees_shared_connection_and_transactions(db):
    a, org = await make_org_with_owner(db, "a@ocidm.io")
    b = await mk_user(db, "b@ocidm.io", org_id=org, cashbook_access="org")
    conn = await mk_connection(db, a, org_id=org)
    txn = await mk_txn(db, conn)

    conns = await service.list_connections(db, b)
    assert [c.id for c in conns] == [conn.id]  # B sees A's connection

    txns, total = await service.list_transactions(db, b, PlaidTransactionFilters())
    assert total == 1 and txns[0].id == txn.id  # B sees A's transactions


async def test_outsider_sees_nothing(db):
    a, org = await make_org_with_owner(db, "a@ocidm.io")
    # A personal, non-admin user in no org — falls to own-user-id scope.
    outsider = await mk_user(db, "out@other.com", role=Role.TEAM_MEMBER)
    conn = await mk_connection(db, a, org_id=org)
    await mk_txn(db, conn)

    assert await service.list_connections(db, outsider) == []
    _, total = await service.list_transactions(db, outsider, PlaidTransactionFilters())
    assert total == 0


async def test_peer_can_read_but_not_manage_others_connection(db):
    a, org = await make_org_with_owner(db, "a@ocidm.io")
    b = await mk_user(db, "b@ocidm.io", org_id=org, cashbook_access="org")
    conn = await mk_connection(db, a, org_id=org)

    # Read path (used by categorize) allows the peer...
    read = await service.get_connection_for_read(db, conn.id, b)
    assert read.id == conn.id
    # ...but the owner-only path (used by delete / force-sync) does not.
    with pytest.raises(NotFoundError):
        await service.get_connection(db, conn.id, b.id)


async def test_peer_can_categorize_shared_transaction(db):
    a, org = await make_org_with_owner(db, "a@ocidm.io")
    b = await mk_user(db, "b@ocidm.io", org_id=org, cashbook_access="org")
    conn = await mk_connection(db, a, org_id=org)
    txn = await mk_txn(db, conn)

    result = await service.categorize_transaction(
        db, txn.id, CategorizeTransactionRequest(as_type="ignore"), b, SimpleNamespace(),
    )
    assert result.is_categorized is True  # B categorized A's shared txn


# ---------------------------------------------------------------------------
# Search + bulk categorize
# ---------------------------------------------------------------------------


async def test_search_matches_name_case_insensitive(db):
    u = await mk_user(db, "solo@x.com")  # personal
    conn = await mk_connection(db, u, org_id=None)
    await mk_txn(db, conn, name="Tim Hortons")
    await mk_txn(db, conn, name="Starbucks")
    await mk_txn(db, conn, name="TIM HORTONS #4021")

    _, total = await service.list_transactions(db, u, PlaidTransactionFilters(search="tim"))
    assert total == 2  # both Tim Hortons, not Starbucks
    _, none = await service.list_transactions(db, u, PlaidTransactionFilters(search="nomatch"))
    assert none == 0


async def test_bulk_categorize_posts_all_to_cashbook(db):
    from sqlalchemy import func, select
    from app.cashbook.models import CashbookEntry
    from app.integrations.plaid.schemas import BulkCategorizeRequest

    a, org = await make_org_with_owner(db, "a@ocidm.io")
    conn = await mk_connection(db, a, org_id=org)
    t1 = await mk_txn(db, conn, name="Tim Hortons", amount="4.50")
    t2 = await mk_txn(db, conn, name="Tim Hortons", amount="6.25")

    req = BulkCategorizeRequest(txn_ids=[t1.id, t2.id], as_type="cashbook")
    result = await service.bulk_categorize_transactions(db, [t1.id, t2.id], req, a, SimpleNamespace())

    assert result == {"posted": 2, "total": 2, "errors": []}
    n = await db.scalar(
        select(func.count(CashbookEntry.id)).where(
            CashbookEntry.user_id == a.id, CashbookEntry.source == "plaid"
        )
    )
    assert n == 2


# ---------------------------------------------------------------------------
# Plaid keys config — manager-only
# ---------------------------------------------------------------------------

PLAID_URL = "/api/integrations/settings/plaid"


async def _mk_admin(db, email):
    u = User(
        id=uuid.uuid4(), email=email, hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0], role=Role.ADMIN, is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def test_only_manager_sees_and_writes_plaid_keys(client, db, monkeypatch):
    from tests.conftest import TEST_SETTINGS, auth_header

    mgr = await _mk_admin(db, "nathano@ocidm.io")
    other = await _mk_admin(db, "shivonneo@ocidm.io")
    monkeypatch.setattr(TEST_SETTINGS, "plaid_config_manager_email", "nathano@ocidm.io")

    # Manager seeds the config.
    r = await client.put(
        PLAID_URL,
        json={"config": {"client_id": "cid1234567890", "secret": "sekabcdefghij", "environment": "production"}},
        headers=auth_header(mgr),
    )
    assert r.status_code == 200

    # Manager GET: can_manage True + masked keys present.
    rm = await client.get(PLAID_URL, headers=auth_header(mgr))
    assert rm.json()["meta"]["can_manage_config"] is True
    assert rm.json()["data"]["client_id"].startswith("****")

    # Other operator GET: can_manage False + NO keys leaked.
    ro = await client.get(PLAID_URL, headers=auth_header(other))
    assert ro.json()["meta"]["can_manage_config"] is False
    assert ro.json()["data"]["client_id"] == ""
    assert ro.json()["data"]["secret"] == ""

    # Other operator PUT: refused.
    rw = await client.put(PLAID_URL, json={"config": {"client_id": "hijack"}}, headers=auth_header(other))
    assert rw.status_code == 403
    assert rw.json()["error"]["code"] == "PLAID_CONFIG_OPERATOR_ONLY"
