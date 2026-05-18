"""Email channel of the notification dispatcher.

`create_notification` is the chokepoint for in-app + email + SMS. These
tests verify the email branch:

  - fires when prefs.email=True, skips when prefs.email=False
  - never blocks the in-app row, even when SMTP raises
  - skips cleanly when no SMTP config exists (no surfaced error)

We monkeypatch the SMTP send so nothing dials out.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.encryption import init_encryption_service
from app.email.models import SmtpConfig
from app.notifications.models import Notification, NotificationPreference
from app.notifications.service import create_notification
from tests.conftest import TEST_SETTINGS

# Encrypt SmtpConfig.password requires the global Fernet service. Other
# SMTP-touching test modules do the same — initialize at module-load so
# every test in this file has a working get_encryption_service().
init_encryption_service(TEST_SETTINGS.fernet_key)


@pytest_asyncio.fixture
async def smtp_config(db: AsyncSession, admin_user: User) -> SmtpConfig:
    """A minimal SMTP config owned by admin_user. The encrypted_password
    is just bytes — we never decrypt because we stub send_email."""
    from app.core.encryption import get_encryption_service

    cfg = SmtpConfig(
        id=uuid.uuid4(),
        name="Test SMTP",
        host="smtp.example.com",
        port=587,
        username="noreply@example.com",
        encrypted_password=get_encryption_service().encrypt("dummy"),
        from_email="noreply@example.com",
        from_name="Accountant Test",
        use_tls=True,
        is_default=True,
        created_by=admin_user.id,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@pytest_asyncio.fixture
async def capture_email_sends(monkeypatch):
    """Replace email.service.send_email with an in-memory recorder so we
    can assert what would have gone out. Stub MUST be installed where the
    helper looks it up (inside _send_email_notification), not at the
    point of import — Python rebinds attributes by reference."""
    sent: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sent.append({
            "to": to,
            "subject": subject,
            "html_body": html_body,
        })

    monkeypatch.setattr("app.email.service.send_email", _stub_send)
    return sent


@pytest.mark.high
async def test_email_channel_fires_when_pref_enabled(
    db: AsyncSession,
    admin_user: User,
    smtp_config: SmtpConfig,
    capture_email_sends: list[dict],
):
    """type='password_changed' defaults to email=True. With an SMTP
    config in scope, create_notification must produce an outbound email."""
    notification = await create_notification(
        db,
        user_id=admin_user.id,
        type="password_changed",
        title="Password changed",
        message="Your password was reset.",
        link_path="/settings?tab=profile",
    )

    assert notification is not None
    assert len(capture_email_sends) == 1
    sent = capture_email_sends[0]
    assert sent["to"] == admin_user.email
    assert "Password changed" in sent["subject"]
    # The link_path should be expanded against public_base_url and
    # surface as a clickable CTA in the rendered HTML.
    assert "/settings?tab=profile" in sent["html_body"]


@pytest.mark.high
async def test_email_channel_skipped_when_pref_disabled(
    db: AsyncSession,
    admin_user: User,
    smtp_config: SmtpConfig,
    capture_email_sends: list[dict],
):
    """A user-overridden pref of email=False must squash the send even
    when DEFAULT_PREFERENCES would have it enabled."""
    db.add(NotificationPreference(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        notification_type="password_changed",
        in_app=True,
        email=False,  # override the default
        sms=False,
    ))
    await db.commit()

    await create_notification(
        db,
        user_id=admin_user.id,
        type="password_changed",
        title="Password changed",
        message="Your password was reset.",
    )

    assert capture_email_sends == []


@pytest.mark.high
async def test_smtp_failure_does_not_block_in_app_row(
    db: AsyncSession,
    admin_user: User,
    smtp_config: SmtpConfig,
    monkeypatch,
):
    """If SMTP raises (offline mailbox, auth failure, anything), the
    in-app notification row MUST still be created. This is the contract
    that lets us turn on the email channel without fearing it'll black-
    hole bell-notifications during an outage."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("smtp server unreachable")

    monkeypatch.setattr("app.email.service.send_email", _boom)

    notification = await create_notification(
        db,
        user_id=admin_user.id,
        type="password_changed",
        title="Password changed",
        message="Your password was reset.",
    )

    # In-app row exists despite SMTP blowup.
    assert notification is not None
    rows = await db.execute(
        select(Notification).where(Notification.user_id == admin_user.id)
    )
    assert len(list(rows.scalars().all())) == 1


@pytest.mark.normal
async def test_no_smtp_config_skips_cleanly(
    db: AsyncSession,
    admin_user: User,
    capture_email_sends: list[dict],
):
    """No user SMTP config AND no system default = email channel becomes
    a quiet no-op. Test verifies we don't raise NotFoundError up through
    the dispatcher."""
    # No smtp_config fixture used — nothing in the DB.
    notification = await create_notification(
        db,
        user_id=admin_user.id,
        type="password_changed",
        title="Password changed",
        message="Your password was reset.",
    )
    assert notification is not None  # in-app still works
    assert capture_email_sends == []  # email gracefully skipped
