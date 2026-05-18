"""Welcome email — fires on registration + on admin-invite, never
blocks account creation when SMTP misbehaves.

Goes through the Tier 2 override renderer so admins can customize the
copy via Settings → Email Templates without a code change.
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


@pytest.mark.high
async def test_welcome_email_sent_on_register(
    client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
):
    """First-time registration must dispatch a welcome email after the
    user row commits. Requires NO existing users — register is locked
    to bootstrap-only per app/auth/service.py."""
    # Capture welcome calls at the service layer rather than at
    # send_email, since SMTP isn't configured in this test and we don't
    # want to thread an SmtpConfig through. Patching the helper directly
    # is the right granularity — we're verifying the wiring fires.
    sent_calls: list[dict] = []

    async def _capture(_db, user, _settings):
        sent_calls.append({"email": user.email, "name": user.full_name})

    monkeypatch.setattr("app.auth.service.send_welcome_email", _capture)

    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "founder@example.com",
            "password": "FirstUser123!",
            "full_name": "First User",
        },
    )
    assert resp.status_code == 201, resp.text
    assert len(sent_calls) == 1
    assert sent_calls[0]["email"] == "founder@example.com"
    assert sent_calls[0]["name"] == "First User"


@pytest.mark.high
async def test_welcome_email_sent_on_admin_create_user_with_invite(
    client: AsyncClient,
    db: AsyncSession,
    admin_user: User,
    monkeypatch,
):
    """When admin creates a user with send_invite=true, BOTH emails
    fire: the invite (Tier 1D) and the welcome (Tier 3). Two separate
    SMTP send calls."""
    # Seed an SMTP config owned by the admin so the invite path's
    # resolve_smtp_config + welcome path's resolve_smtp_config both
    # succeed. Welcome resolves against the NEW user (not admin), so
    # we set is_default=True for system fallback.
    from app.core.encryption import get_encryption_service

    db.add(SmtpConfig(
        id=uuid.uuid4(),
        name="Default",
        host="smtp.example.com",
        port=587,
        username="noreply@example.com",
        encrypted_password=get_encryption_service().encrypt("dummy"),
        from_email="noreply@example.com",
        from_name="Accountant Test",
        use_tls=True,
        is_default=True,
        created_by=admin_user.id,
    ))
    await db.commit()

    sends: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sends.append({"to": to, "subject": subject})

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    resp = await client.post(
        "/api/auth/users",
        json={
            "email": "newhire@example.com",
            "full_name": "New Hire",
            "role": "viewer",
            "send_invite": True,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text

    # Two sends: invite + welcome
    assert len(sends) == 2, f"Expected invite + welcome, got: {sends}"
    invite_sent = next(
        (s for s in sends if "invite" in s["subject"].lower()), None
    )
    welcome_sent = next(
        (s for s in sends if "welcome" in s["subject"].lower()), None
    )
    assert invite_sent is not None, "Invite email missing"
    assert welcome_sent is not None, "Welcome email missing"
    assert invite_sent["to"] == "newhire@example.com"
    assert welcome_sent["to"] == "newhire@example.com"


@pytest.mark.high
async def test_account_creation_succeeds_when_welcome_email_fails(
    client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
):
    """SMTP blowing up during welcome must NEVER fail registration.
    The user row must persist; simulate SMTP failure and verify the
    user is in the DB anyway."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("smtp connection refused")

    monkeypatch.setattr("app.auth.service.send_welcome_email", _boom)

    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "founder2@example.com",
            "password": "FirstUser123!",
            "full_name": "Resilient Founder",
        },
    )
    assert resp.status_code == 201, resp.text

    rows = await db.execute(
        select(User).where(User.email == "founder2@example.com")
    )
    assert rows.scalar_one_or_none() is not None
