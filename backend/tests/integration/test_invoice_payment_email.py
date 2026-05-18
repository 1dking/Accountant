"""Invoice payment → payment_confirmation email hook.

When recording a payment that flips the invoice to PAID, we should
dispatch a confirmation to the contact. Partial payments must NOT
trigger the email (would be a stream of "$300 received" notes during a
multi-payment plan).
"""
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio

from app.auth.models import User
from app.core.encryption import init_encryption_service
from app.invoicing.models import Invoice
from app.invoicing.schemas import InvoicePaymentCreate
from app.invoicing.service import record_payment
from tests.conftest import TEST_SETTINGS

init_encryption_service(TEST_SETTINGS.fernet_key)


@pytest_asyncio.fixture
async def smtp_default(db, admin_user):
    """Default SMTP so resolve_smtp_config() succeeds."""
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
async def test_full_payment_triggers_confirmation_email(
    db,
    admin_user: User,
    sample_invoice: Invoice,
    smtp_default,
    monkeypatch,
):
    """Recording a payment equal to the invoice total flips status to
    PAID and fires the confirmation email."""
    sends: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sends.append({"to": to, "subject": subject, "html_body": html_body})

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    payment_data = InvoicePaymentCreate(
        amount=Decimal(str(sample_invoice.total)),
        date=date.today(),
        payment_method="bank_transfer",
        reference="WIRE-001",
        notes=None,
    )
    await record_payment(db, sample_invoice.id, payment_data, admin_user)

    assert len(sends) == 1, "Expected one confirmation email on PAID transition"
    sent = sends[0]
    # sample_contact.email is "john@acme.com" per conftest
    assert sent["to"] == "john@acme.com"
    assert "Payment received" in sent["subject"]
    assert sample_invoice.invoice_number in sent["subject"]


@pytest.mark.high
async def test_partial_payment_does_not_trigger_email(
    db,
    admin_user: User,
    sample_invoice: Invoice,
    smtp_default,
    monkeypatch,
):
    """A payment of less than the total leaves the invoice in
    PARTIALLY_PAID — no email should fire. Otherwise users on payment
    plans would get a confirmation for every check that clears."""
    sends: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sends.append(subject)

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    half = Decimal(str(sample_invoice.total)) / Decimal("2")
    await record_payment(
        db,
        sample_invoice.id,
        InvoicePaymentCreate(
            amount=half, date=date.today(), payment_method="check",
            reference=None, notes=None,
        ),
        admin_user,
    )

    assert sends == [], "Partial payment should not fire confirmation"


@pytest.mark.normal
async def test_payment_email_failure_does_not_block_record(
    db,
    admin_user: User,
    sample_invoice: Invoice,
    smtp_default,
    monkeypatch,
):
    """If the SMTP call raises, the InvoicePayment row + the PAID status
    transition must persist. Same contract as notifications — email is
    best-effort, the source-of-truth write is the DB."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("app.email.service.send_email", _boom)

    payment = await record_payment(
        db,
        sample_invoice.id,
        InvoicePaymentCreate(
            amount=Decimal(str(sample_invoice.total)),
            date=date.today(),
            payment_method="bank_transfer",
            reference=None, notes=None,
        ),
        admin_user,
    )
    assert payment is not None
    await db.refresh(sample_invoice)
    # Invoice should still be marked paid.
    assert sample_invoice.status.value == "paid"
