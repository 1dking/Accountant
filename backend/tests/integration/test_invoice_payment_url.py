"""Invoice emails must carry a working "Pay Now" button.

Stripe checkout was fully implemented, but nothing ever populated `payment_url`
— the portal hardcoded None and the email service never passed the variable at
all. Both templates gate the button on `{% if payment_url %}`, so it silently
never rendered and customers had no way to pay from the email.
"""
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio

from app.auth.models import User
from app.core.encryption import init_encryption_service
from app.email.service import send_invoice_email
from app.invoicing.models import Invoice, InvoiceStatus
from tests.conftest import TEST_SETTINGS

init_encryption_service(TEST_SETTINGS.fernet_key)


@pytest_asyncio.fixture
async def smtp_default(db, admin_user):
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


@pytest.fixture
def captured_email(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sent.append({"to": to, "subject": subject, "body": html_body})

    monkeypatch.setattr("app.email.service.send_email", _stub_send)
    return sent


@pytest.mark.critical
async def test_invoice_email_includes_pay_now_link(
    db, admin_user: User, sample_invoice: Invoice, smtp_default, captured_email, monkeypatch
):
    """When Stripe is configured, the invoice email must carry the checkout URL."""

    async def _fake_ensure(db_, invoice_id, user, settings, base_url=""):
        return "https://checkout.stripe.com/pay/cs_test_123"

    monkeypatch.setattr(
        "app.integrations.stripe.service.ensure_payment_url", _fake_ensure
    )

    await send_invoice_email(
        db, sample_invoice.id, None, "buyer@test.com", None, None, admin_user
    )

    assert len(captured_email) == 1
    body = captured_email[0]["body"]
    assert "https://checkout.stripe.com/pay/cs_test_123" in body
    assert "Pay Now" in body


@pytest.mark.critical
async def test_paid_invoice_gets_no_pay_button(
    db, admin_user: User, sample_invoice: Invoice, smtp_default, captured_email, monkeypatch
):
    """Inviting someone to pay an invoice they already paid is a real support
    ticket. Never mint a link for a settled invoice."""
    calls: list = []

    async def _fake_ensure(db_, invoice_id, user, settings, base_url=""):
        calls.append(invoice_id)
        return "https://checkout.stripe.com/pay/cs_test_123"

    monkeypatch.setattr(
        "app.integrations.stripe.service.ensure_payment_url", _fake_ensure
    )

    sample_invoice.status = InvoiceStatus.PAID
    await db.commit()

    await send_invoice_email(
        db, sample_invoice.id, None, "buyer@test.com", None, None, admin_user
    )

    assert calls == [], "must not even ask Stripe for a link on a paid invoice"
    assert "Pay Now" not in captured_email[0]["body"]


@pytest.mark.high
async def test_stripe_outage_does_not_block_the_invoice_email(
    db, admin_user: User, sample_invoice: Invoice, smtp_default, captured_email, monkeypatch
):
    """A payment provider being down must degrade to "no button", not "no invoice"."""

    def _explode(settings):
        raise RuntimeError("stripe is down")

    # Force the real ensure_payment_url down its failure path.
    monkeypatch.setattr(TEST_SETTINGS, "stripe_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(
        "app.integrations.stripe.service.create_checkout_session",
        _explode,
    )

    await send_invoice_email(
        db, sample_invoice.id, None, "buyer@test.com", None, None, admin_user
    )

    assert len(captured_email) == 1, "the invoice must still go out"
    assert "Pay Now" not in captured_email[0]["body"]


@pytest.mark.high
async def test_portal_surfaces_pending_payment_link(
    db, admin_user: User, sample_invoice: Invoice, sample_contact
):
    """The portal hardcoded payment_url=None, so the Pay button never rendered
    there either."""
    from app.contacts.models import ClientPortalAccount
    from app.integrations.stripe.models import PaymentLinkStatus, StripePaymentLink
    from app.portal.service import get_portal_invoices

    db.add(
        StripePaymentLink(
            id=uuid.uuid4(),
            invoice_id=sample_invoice.id,
            checkout_session_id="cs_test_abc",
            payment_url="https://checkout.stripe.com/pay/cs_test_abc",
            amount=Decimal("100.00"),
            currency="USD",
            status=PaymentLinkStatus.PENDING,
            created_by=admin_user.id,
        )
    )

    portal_user = User(
        id=uuid.uuid4(),
        email="client@test.com",
        full_name="Client",
        hashed_password="x",
        role=admin_user.role,
        is_active=True,
    )
    db.add(portal_user)
    await db.flush()
    db.add(
        ClientPortalAccount(
            id=uuid.uuid4(),
            user_id=portal_user.id,
            contact_id=sample_contact.id,
            is_active=True,
        )
    )
    await db.commit()

    rows = await get_portal_invoices(db, portal_user)
    row = next(r for r in rows if r["id"] == sample_invoice.id)
    assert row["payment_url"] == "https://checkout.stripe.com/pay/cs_test_abc"
