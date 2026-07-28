"""Platform Plaid credentials are operator-only to write.

They are OCIDM's shared production keys. Because self-serve signups become ADMIN
of their own tenant, the role gate alone would let any tenant admin overwrite
them. These tests pin: once the Plaid Link allow-list is set, only those
operators can write the Plaid config; an empty allow-list preserves the
pre-go-live admin flow; and other integrations are unaffected.
"""
import uuid

import pytest
from cryptography.fernet import Fernet

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.core.encryption import init_encryption_service

PLAID_URL = "/api/integrations/settings/plaid"
PLAID_CFG = {"config": {"client_id": "cid", "secret": "sek", "environment": "sandbox"}}


@pytest.fixture(autouse=True)
def _encryption():
    init_encryption_service(Fernet.generate_key().decode())


async def mk_admin(db, email: str) -> User:
    u = User(
        id=uuid.uuid4(), email=email, hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0], role=Role.ADMIN, is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def test_allowlisted_operator_can_write_plaid_config(client, db, monkeypatch):
    from tests.conftest import TEST_SETTINGS, auth_header

    op = await mk_admin(db, "operator@ocidm.io")
    monkeypatch.setattr(TEST_SETTINGS, "plaid_link_allowed_emails", "operator@ocidm.io")

    r = await client.put(PLAID_URL, json=PLAID_CFG, headers=auth_header(op))
    assert r.status_code == 200


async def test_non_allowlisted_tenant_admin_cannot_write_plaid_config(client, db, monkeypatch):
    from tests.conftest import TEST_SETTINGS, auth_header

    tenant = await mk_admin(db, "tenant@customer.com")
    monkeypatch.setattr(TEST_SETTINGS, "plaid_link_allowed_emails", "operator@ocidm.io")

    r = await client.put(PLAID_URL, json={"config": {"client_id": "hijack"}},
                         headers=auth_header(tenant))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PLAID_CONFIG_OPERATOR_ONLY"


async def test_empty_allowlist_preserves_admin_write(client, db, monkeypatch):
    from tests.conftest import TEST_SETTINGS, auth_header

    admin = await mk_admin(db, "someadmin@test.com")
    monkeypatch.setattr(TEST_SETTINGS, "plaid_link_allowed_emails", "")

    r = await client.put(PLAID_URL, json=PLAID_CFG, headers=auth_header(admin))
    assert r.status_code == 200  # unconfigured -> pre-go-live behaviour unchanged


async def test_plaid_lock_does_not_affect_other_integrations(client, db, monkeypatch):
    from tests.conftest import TEST_SETTINGS, auth_header

    tenant = await mk_admin(db, "tenant@customer.com")
    monkeypatch.setattr(TEST_SETTINGS, "plaid_link_allowed_emails", "operator@ocidm.io")

    # A non-operator admin can still manage e.g. Twilio (role-only gate as before).
    r = await client.put("/api/integrations/settings/twilio",
                         json={"config": {"account_sid": "AC1", "auth_token": "tok"}},
                         headers=auth_header(tenant))
    assert r.status_code == 200
