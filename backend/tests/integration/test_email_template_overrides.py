"""Editable email template overrides — renderer + admin endpoints.

Coverage:
  1. render_email falls back to system Jinja2 when no override
  2. render_email substitutes {placeholder} when override present
  3. render_email HTML-escapes injected values (XSS guard)
  4. PUT/GET/DELETE round-trip
  5. POST test endpoint dispatches via SMTP
  6. Override scoped per-user (A's override doesn't leak to B's renders)
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.core.encryption import init_encryption_service
from app.email.models import EmailTemplateOverride, SmtpConfig
from app.email.renderer import render_email
from tests.conftest import TEST_SETTINGS, auth_header

init_encryption_service(TEST_SETTINGS.fernet_key)


@pytest_asyncio.fixture
async def smtp_default(db, admin_user):
    from app.core.encryption import get_encryption_service

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
async def test_render_falls_back_to_system_when_no_override(
    db: AsyncSession, admin_user: User
):
    """Without an override row, render_email returns the schema default
    subject and the Jinja2-rendered system template."""
    subject, body = await render_email(
        db,
        "password_reset",
        admin_user.id,
        user_name="Jane",
        reset_url="https://example.com/reset/abc",
        expires_in="1 hour",
        company_name="Accountant",
        year=2026,
    )
    assert subject == "Reset your password"
    # System template references {{ user_name }} in Jinja2 syntax.
    assert "Jane" in body
    assert "https://example.com/reset/abc" in body


@pytest.mark.high
async def test_override_substitutes_placeholders(
    db: AsyncSession, admin_user: User
):
    """When an override is saved, render_email uses {placeholder}
    substitution (NOT Jinja2) on the override body."""
    db.add(EmailTemplateOverride(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        template_key="password_reset",
        subject_override="Hey {user_name}, password reset inside",
        body_override=(
            "<p>Hi {user_name},</p>"
            "<p>Click here: {reset_url}</p>"
            "<p>Expires in {expires_in}.</p>"
        ),
    ))
    await db.commit()

    subject, body = await render_email(
        db,
        "password_reset",
        admin_user.id,
        user_name="Jane",
        reset_url="https://example.com/reset/abc",
        expires_in="1 hour",
        company_name="Accountant",
        year=2026,
    )
    assert subject == "Hey Jane, password reset inside"
    assert "<p>Hi Jane,</p>" in body
    assert "https://example.com/reset/abc" in body
    assert "Expires in 1 hour" in body
    # Base.html chrome still wraps it.
    assert "<html" in body


@pytest.mark.high
async def test_override_html_escapes_injected_values(
    db: AsyncSession, admin_user: User
):
    """A malicious / weirdly-formed user_name MUST be HTML-escaped at
    substitution time so it can't break out of the placeholder and
    inject markup. This is the XSS guard."""
    db.add(EmailTemplateOverride(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        template_key="password_reset",
        body_override="<p>Hi {user_name}, click {reset_url}</p>",
    ))
    await db.commit()

    _, body = await render_email(
        db,
        "password_reset",
        admin_user.id,
        user_name="<script>alert(1)</script>",
        reset_url="https://example.com/safe",
        expires_in="1 hour",
        company_name="Accountant",
        year=2026,
    )
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body
    # URL variable is allowed through unescaped (caller-trusted boundary).
    assert "https://example.com/safe" in body


@pytest.mark.high
async def test_put_get_delete_round_trip(
    client: AsyncClient, admin_user: User, db: AsyncSession
):
    """Admin CRUD on overrides via /api/email/templates/{key}."""
    # Initially empty
    resp = await client.get(
        "/api/email/templates/password_reset",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["subject_override"] is None

    # PUT
    resp = await client.put(
        "/api/email/templates/password_reset",
        json={
            "subject_override": "Custom subject",
            "body_override": "<p>Hi {user_name}</p>",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["subject_override"] == "Custom subject"
    assert body["body_override"] == "<p>Hi {user_name}</p>"
    assert body["is_customized"] is True

    # GET reflects the saved state
    resp = await client.get(
        "/api/email/templates/password_reset",
        headers=auth_header(admin_user),
    )
    assert resp.json()["data"]["subject_override"] == "Custom subject"

    # DELETE
    resp = await client.delete(
        "/api/email/templates/password_reset",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    rows = await db.execute(
        select(EmailTemplateOverride).where(
            EmailTemplateOverride.user_id == admin_user.id,
            EmailTemplateOverride.template_key == "password_reset",
        )
    )
    assert rows.scalar_one_or_none() is None


@pytest.mark.high
async def test_put_rejects_body_override_for_structured_template(
    client: AsyncClient, admin_user: User
):
    """Templates with allows_body_override=False (invoice, payment_reminder,
    estimate) must reject body_override at the API boundary. Subject is
    still editable."""
    resp = await client.put(
        "/api/email/templates/invoice",
        json={
            "subject_override": "Custom invoice subject",
            "body_override": "<p>Custom body</p>",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
    assert "body overrides" in resp.json()["error"]["message"].lower()

    # Subject-only is fine.
    resp = await client.put(
        "/api/email/templates/invoice",
        json={"subject_override": "Custom invoice subject"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200


@pytest.mark.high
async def test_test_send_uses_override(
    client: AsyncClient,
    admin_user: User,
    smtp_default,
    monkeypatch,
):
    """POST /test sends a real email via SMTP using the admin's
    override (or draft passed in the body)."""
    sends: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sends.append({"to": to, "subject": subject, "html_body": html_body})

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    resp = await client.post(
        "/api/email/templates/password_reset/test",
        json={
            "to_email": "admin@test.com",
            "subject_override": "Draft preview subject {user_name}",
            "body_override": "<p>Preview body for {user_name}</p>",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert len(sends) == 1
    sent = sends[0]
    assert sent["to"] == "admin@test.com"
    assert "[TEST]" in sent["subject"]
    assert "Draft preview subject Jane Smith" in sent["subject"]
    assert "Preview body for Jane Smith" in sent["html_body"]


@pytest.mark.normal
async def test_override_scoped_per_user(
    db: AsyncSession, admin_user: User
):
    """Admin A's override must not apply to admin B's renders. We
    create a second admin, save an override on the first, render for
    the second, and assert the system fallback is used."""
    other = User(
        id=uuid.uuid4(),
        email="other-admin@test.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Other Admin",
        role=Role.ADMIN,
        is_active=True,
    )
    db.add(other)
    db.add(EmailTemplateOverride(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        template_key="password_reset",
        subject_override="Only admin_user sees this",
    ))
    await db.commit()

    # admin_user → custom subject
    subj_a, _ = await render_email(
        db, "password_reset", admin_user.id,
        user_name="A", reset_url="https://x", expires_in="1h",
        company_name="X", year=2026,
    )
    assert subj_a == "Only admin_user sees this"

    # other admin → system default
    subj_b, _ = await render_email(
        db, "password_reset", other.id,
        user_name="B", reset_url="https://x", expires_in="1h",
        company_name="X", year=2026,
    )
    assert subj_b == "Reset your password"
