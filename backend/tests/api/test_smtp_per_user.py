"""Tests for per-user SMTP configuration scoping at /api/email/configs."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.encryption import init_encryption_service
from tests.conftest import TEST_SETTINGS, auth_header

# Initialize encryption so SMTP password can be encrypted in tests
init_encryption_service(TEST_SETTINGS.fernet_key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SMTP_PAYLOAD = {
    "name": "My SMTP",
    "host": "smtp.gmail.com",
    "port": 587,
    "username": "user@gmail.com",
    "password": "apppassword",
    "from_email": "user@gmail.com",
    "from_name": "Test User",
    "use_tls": True,
    "is_default": True,
}


def _smtp_payload(**overrides) -> dict:
    """Return a config payload with optional field overrides."""
    return {**SMTP_PAYLOAD, **overrides}


# ---------------------------------------------------------------------------
# 1. Admin creates a config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_smtp_config(client: AsyncClient, admin_user: User):
    """Admin creates an SMTP config and gets back expected fields."""
    resp = await client.post(
        "/api/email/configs",
        json=SMTP_PAYLOAD,
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201 or resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "My SMTP"
    assert data["host"] == "smtp.gmail.com"
    assert data["port"] == 587
    assert data["from_email"] == "user@gmail.com"
    assert data["from_name"] == "Test User"
    assert data["use_tls"] is True
    assert data["is_default"] is True
    assert data["created_by"] == str(admin_user.id)
    assert "id" in data
    assert "created_at" in data


# ---------------------------------------------------------------------------
# 2. Accountant creates own config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accountant_creates_own_config(
    client: AsyncClient, accountant_user: User
):
    """Accountant can create their own SMTP config."""
    resp = await client.post(
        "/api/email/configs",
        json=_smtp_payload(name="Accountant SMTP", username="acct@gmail.com"),
        headers=auth_header(accountant_user),
    )
    assert resp.status_code == 201 or resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Accountant SMTP"
    assert data["created_by"] == str(accountant_user.id)


# ---------------------------------------------------------------------------
# 3. List configs scoped to user (non-admin sees only own)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_configs_scoped_to_user(
    client: AsyncClient, admin_user: User, accountant_user: User
):
    """Accountant lists configs and only sees their own, not admin's."""
    # Admin creates a config
    await client.post(
        "/api/email/configs",
        json=_smtp_payload(name="Admin Config"),
        headers=auth_header(admin_user),
    )
    # Accountant creates a config
    await client.post(
        "/api/email/configs",
        json=_smtp_payload(name="Accountant Config"),
        headers=auth_header(accountant_user),
    )

    # Accountant lists -- should only see own
    resp = await client.get(
        "/api/email/configs",
        headers=auth_header(accountant_user),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) >= 1
    for item in items:
        assert item["created_by"] == str(accountant_user.id)


# ---------------------------------------------------------------------------
# 4. Admin sees all configs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_sees_all_configs(
    client: AsyncClient, admin_user: User, accountant_user: User
):
    """Admin lists configs and sees both their own and other users' configs."""
    # Admin creates a config
    await client.post(
        "/api/email/configs",
        json=_smtp_payload(name="Admin Config"),
        headers=auth_header(admin_user),
    )
    # Accountant creates a config
    await client.post(
        "/api/email/configs",
        json=_smtp_payload(name="Accountant Config"),
        headers=auth_header(accountant_user),
    )

    # Admin lists -- should see both
    resp = await client.get(
        "/api/email/configs",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    creators = {item["created_by"] for item in items}
    assert str(admin_user.id) in creators
    assert str(accountant_user.id) in creators


# ---------------------------------------------------------------------------
# 5. Viewer cannot create config (403)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_viewer_cannot_create_config(
    client: AsyncClient, viewer_user: User
):
    """Viewer role is not permitted to create SMTP configs."""
    resp = await client.post(
        "/api/email/configs",
        json=SMTP_PAYLOAD,
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# 6. Setting is_default unsets previous default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_default_unsets_previous(
    client: AsyncClient, admin_user: User
):
    """Creating a second config with is_default=True unsets the first."""
    headers = auth_header(admin_user)

    # Create first config as default
    resp1 = await client.post(
        "/api/email/configs",
        json=_smtp_payload(name="First Default", is_default=True),
        headers=headers,
    )
    first_id = resp1.json()["data"]["id"]

    # Create second config as default
    resp2 = await client.post(
        "/api/email/configs",
        json=_smtp_payload(name="Second Default", is_default=True),
        headers=headers,
    )
    second_id = resp2.json()["data"]["id"]

    # List and verify only the second is default
    resp = await client.get("/api/email/configs", headers=headers)
    items = resp.json()["data"]
    for item in items:
        if item["id"] == first_id:
            assert item["is_default"] is False, "First config should no longer be default"
        if item["id"] == second_id:
            assert item["is_default"] is True, "Second config should be the default"


# ---------------------------------------------------------------------------
# 7. Unauthenticated request gets 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_gets_401(client: AsyncClient):
    """GET /api/email/configs without a token returns 401."""
    resp = await client.get("/api/email/configs")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 8. Delete own config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_config_own(client: AsyncClient, admin_user: User):
    """User can delete their own SMTP config."""
    headers = auth_header(admin_user)

    # Create
    resp = await client.post(
        "/api/email/configs",
        json=_smtp_payload(name="To Delete"),
        headers=headers,
    )
    config_id = resp.json()["data"]["id"]

    # Delete
    resp = await client.delete(
        f"/api/email/configs/{config_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Verify it is gone from list
    resp = await client.get("/api/email/configs", headers=headers)
    ids = [item["id"] for item in resp.json()["data"]]
    assert config_id not in ids
