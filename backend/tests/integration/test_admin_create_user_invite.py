"""POST /api/auth/users — invite email path.

The endpoint used to silently drop send_invite=true (just created the
user, never emailed). These tests pin the new behavior: send_invite
triggers an invite email AND the response always carries invite_link
as a fallback for SMTP failures.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.models import User
from app.core.encryption import init_encryption_service
from tests.conftest import TEST_SETTINGS, auth_header

init_encryption_service(TEST_SETTINGS.fernet_key)


@pytest_asyncio.fixture
async def smtp_default(db, admin_user):
    """Default SMTP owned by admin so resolve_smtp_config succeeds."""
    import uuid
    from app.core.encryption import get_encryption_service
    from app.email.models import SmtpConfig

    cfg = SmtpConfig(
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
    )
    db.add(cfg)
    await db.commit()
    return cfg


@pytest.mark.high
async def test_send_invite_true_triggers_email(
    client: AsyncClient,
    admin_user: User,
    smtp_default,
    monkeypatch,
):
    """send_invite=true must render invite.html + dispatch via SMTP.
    Response must also carry invite_link so the admin has a manual copy."""
    sends: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sends.append({
            "to": to,
            "subject": subject,
            "html_body": html_body,
        })

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
    body = resp.json()["data"]
    assert body["email"] == "newhire@example.com"
    assert body.get("invite_link"), "Response must include invite_link fallback"
    assert "/invite?token=" in body["invite_link"]

    assert len(sends) == 1
    sent = sends[0]
    assert sent["to"] == "newhire@example.com"
    assert "invite" in sent["subject"].lower()
    assert "New Hire" in sent["html_body"]


@pytest.mark.normal
async def test_send_invite_false_skips_email(
    client: AsyncClient,
    admin_user: User,
    smtp_default,
    monkeypatch,
):
    """The legacy path (password provided, send_invite omitted) must
    not fire any email — we don't want every admin-created user to
    receive a surprise invite when the admin just typed a password."""
    sends: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sends.append(subject)

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    resp = await client.post(
        "/api/auth/users",
        json={
            "email": "newhire2@example.com",
            "password": "TempPass123!",
            "full_name": "Old Path",
            "role": "viewer",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    assert sends == []


@pytest.mark.normal
async def test_invite_smtp_failure_does_not_block_create(
    client: AsyncClient,
    admin_user: User,
    smtp_default,
    monkeypatch,
):
    """If SMTP blows up, the user must still be created and the
    invite_link must still be in the response so the admin can ferry
    it manually."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("smtp unavailable")

    monkeypatch.setattr("app.email.service.send_email", _boom)

    resp = await client.post(
        "/api/auth/users",
        json={
            "email": "newhire3@example.com",
            "full_name": "Third Hire",
            "role": "viewer",
            "send_invite": True,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["invite_link"]
