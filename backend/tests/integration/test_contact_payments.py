"""Contact → Payments tab.

The tab existed in the UI but rendered "Payments coming soon". Payments hang
off the invoice, not the contact, so this joins through Invoice.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.auth.models import User
from app.contacts.service import list_contact_payments
from app.invoicing.models import Invoice, InvoicePayment
from tests.conftest import auth_header


@pytest.mark.high
async def test_lists_payments_across_the_contacts_invoices(
    db, admin_user: User, sample_contact, sample_invoice: Invoice
):
    db.add_all(
        [
            InvoicePayment(
                id=uuid.uuid4(),
                invoice_id=sample_invoice.id,
                amount=Decimal("40.00"),
                date=date(2026, 3, 1),
                payment_method="bank_transfer",
                reference="WIRE-1",
                recorded_by=admin_user.id,
            ),
            InvoicePayment(
                id=uuid.uuid4(),
                invoice_id=sample_invoice.id,
                amount=Decimal("60.00"),
                date=date(2026, 3, 9),
                payment_method="card",
                reference="CARD-2",
                recorded_by=admin_user.id,
            ),
        ]
    )
    await db.commit()

    rows = await list_contact_payments(db, sample_contact.id, user=admin_user)

    assert len(rows) == 2
    # Newest first.
    assert rows[0]["reference"] == "CARD-2"
    assert rows[0]["amount"] == 60.0
    assert rows[0]["invoice_number"] == sample_invoice.invoice_number
    assert sum(r["amount"] for r in rows) == 100.0


@pytest.mark.high
async def test_contact_with_no_payments_returns_empty(
    db, admin_user: User, sample_contact
):
    assert await list_contact_payments(db, sample_contact.id, user=admin_user) == []


@pytest.mark.high
async def test_payments_endpoint_is_reachable(
    client, admin_user: User, sample_contact, sample_invoice: Invoice, db
):
    db.add(
        InvoicePayment(
            id=uuid.uuid4(),
            invoice_id=sample_invoice.id,
            amount=Decimal("25.00"),
            date=date(2026, 4, 2),
            payment_method="cash",
            recorded_by=admin_user.id,
        )
    )
    await db.commit()

    resp = await client.get(
        f"/api/contacts/{sample_contact.id}/payments", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["amount"] == 25.0
    assert data[0]["payment_method"] == "cash"


@pytest.mark.critical
async def test_payments_require_authentication(client, sample_contact):
    resp = await client.get(f"/api/contacts/{sample_contact.id}/payments")
    assert resp.status_code == 401
