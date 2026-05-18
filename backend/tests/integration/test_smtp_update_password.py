"""Editing an SMTP config must preserve the stored password unless
the admin explicitly typed a new one.

Two paths the frontend could produce:
  - omits the `password` key entirely from the PUT body (preferred)
  - sends `"password": null` (defensive: form-state coercion mishap)

Both must leave config.encrypted_password unchanged. The service
guard is the belt-and-suspenders against the null case.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.encryption import init_encryption_service
from app.email.models import SmtpConfig
from tests.conftest import TEST_SETTINGS, auth_header

init_encryption_service(TEST_SETTINGS.fernet_key)


@pytest_asyncio.fixture
async def existing_config(db: AsyncSession, admin_user: User) -> SmtpConfig:
    """Seed an SMTP config with a known encrypted password we can
    inspect after the update."""
    from app.core.encryption import get_encryption_service

    cfg = SmtpConfig(
        id=uuid.uuid4(),
        name="Original Name",
        host="smtp.example.com",
        port=587,
        username="noreply@example.com",
        encrypted_password=get_encryption_service().encrypt("ORIGINAL_PASSWORD"),
        from_email="noreply@example.com",
        from_name="Accountant",
        use_tls=True,
        is_default=True,
        created_by=admin_user.id,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@pytest.mark.high
async def test_smtp_update_preserves_password_when_omitted(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    existing_config: SmtpConfig,
):
    """PUT without a 'password' key in the body must leave the
    encrypted password byte-identical."""
    from app.core.encryption import get_encryption_service

    original_ciphertext = existing_config.encrypted_password

    resp = await client.put(
        f"/api/email/configs/{existing_config.id}",
        json={"from_name": "Renamed Accountant"},  # no password key
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["from_name"] == "Renamed Accountant"

    # Re-fetch from DB and assert password decrypts to the original.
    # Identity-map workaround: the route runs in a separate session, so
    # we have to expire the fixture-loaded row to force a fresh SELECT.
    await db.refresh(existing_config)
    assert existing_config.encrypted_password == original_ciphertext, (
        "Ciphertext changed despite no password in PUT body"
    )
    assert get_encryption_service().decrypt(existing_config.encrypted_password) == "ORIGINAL_PASSWORD"


@pytest.mark.high
async def test_smtp_update_preserves_password_when_null(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    existing_config: SmtpConfig,
):
    """PUT with explicit "password": null must NOT crash and must NOT
    wipe the stored password. This is the edge case the frontend can
    accidentally produce by spreading form state where blanks coerce
    to null."""
    from app.core.encryption import get_encryption_service

    original_ciphertext = existing_config.encrypted_password

    resp = await client.put(
        f"/api/email/configs/{existing_config.id}",
        json={"from_name": "Renamed Again", "password": None},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    await db.refresh(existing_config)
    assert existing_config.encrypted_password == original_ciphertext, (
        "Ciphertext changed despite password=null in PUT body"
    )
    assert get_encryption_service().decrypt(existing_config.encrypted_password) == "ORIGINAL_PASSWORD"


@pytest.mark.normal
async def test_smtp_update_changes_password_when_provided(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    existing_config: SmtpConfig,
):
    """Sanity-check the positive path — a real new password DOES land.
    Locks in the guard against over-correcting (e.g. someone tightens
    the if-truthy check and the new password silently gets dropped)."""
    from app.core.encryption import get_encryption_service

    resp = await client.put(
        f"/api/email/configs/{existing_config.id}",
        json={"password": "BRAND_NEW_PASSWORD"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    await db.refresh(existing_config)
    assert get_encryption_service().decrypt(existing_config.encrypted_password) == "BRAND_NEW_PASSWORD"
