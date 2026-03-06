"""Tests for the invoicing API (/api/invoices) and estimate-to-invoice conversion.

Covers: CRUD, math verification, role-based access, status transitions,
payments (partial + full), stats, and estimate conversion.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from tests.conftest import auth_header

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY = date.today()
_DUE = _TODAY + timedelta(days=30)


def _invoice_payload(
    contact_id: uuid.UUID,
    *,
    line_items: list[dict] | None = None,
    tax_rate: str | None = "10.00",
    discount_amount: str = "0.0",
    currency: str = "USD",
    notes: str | None = None,
    payment_terms: str | None = None,
) -> dict:
    """Return a valid InvoiceCreate JSON body."""
    if line_items is None:
        line_items = [
            {
                "description": "Consulting Services",
                "quantity": "10",
                "unit_price": "150.00",
            }
        ]
    return {
        "contact_id": str(contact_id),
        "issue_date": _TODAY.isoformat(),
        "due_date": _DUE.isoformat(),
        "tax_rate": tax_rate,
        "discount_amount": discount_amount,
        "currency": currency,
        "notes": notes,
        "payment_terms": payment_terms,
        "line_items": line_items,
    }


def _estimate_payload(
    contact_id: uuid.UUID,
    *,
    line_items: list[dict] | None = None,
    tax_rate: str | None = "10.00",
    discount_amount: str = "0.0",
) -> dict:
    """Return a valid EstimateCreate JSON body."""
    if line_items is None:
        line_items = [
            {
                "description": "Design Work",
                "quantity": "5",
                "unit_price": "200.00",
            }
        ]
    return {
        "contact_id": str(contact_id),
        "issue_date": _TODAY.isoformat(),
        "expiry_date": _DUE.isoformat(),
        "tax_rate": tax_rate,
        "discount_amount": discount_amount,
        "currency": "USD",
        "notes": "Estimate notes",
        "line_items": line_items,
    }


async def _create_invoice(
    client: AsyncClient,
    user: User,
    contact_id: uuid.UUID,
    **overrides,
) -> dict:
    """POST an invoice and return the response JSON ``data`` dict."""
    payload = _invoice_payload(contact_id, **overrides)
    resp = await client.post(
        "/api/invoices", json=payload, headers=auth_header(user)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# =========================================================================
# 1. Create invoice — verify math
# =========================================================================


@pytest.mark.critical
async def test_create_invoice_math(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Single line item: subtotal = qty * unit_price, tax applied, discount zero."""
    data = await _create_invoice(client, admin_user, sample_contact.id)

    # Line: 10 x $150 = $1500.00
    assert Decimal(str(data["subtotal"])) == Decimal("1500.00")
    # Tax: 10% of 1500 = $150.00
    assert Decimal(str(data["tax_amount"])) == Decimal("150.00")
    # Discount is 0
    assert Decimal(str(data["discount_amount"])) == Decimal("0.00")
    # Total = 1500 + 150 - 0 = $1650.00
    assert Decimal(str(data["total"])) == Decimal("1650.00")
    assert data["status"] == "draft"
    assert data["currency"] == "USD"
    # Must have an auto-generated invoice number
    assert data["invoice_number"].startswith("INV-")


# =========================================================================
# 2. Create invoice with multiple line items — verify each line total
# =========================================================================


@pytest.mark.critical
async def test_create_invoice_multiple_line_items(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Multiple line items: verify per-line totals and aggregate subtotal."""
    items = [
        {"description": "Widget A", "quantity": "3", "unit_price": "25.00"},
        {"description": "Widget B", "quantity": "2", "unit_price": "50.00"},
        {"description": "Widget C", "quantity": "1", "unit_price": "200.00"},
    ]
    data = await _create_invoice(
        client,
        admin_user,
        sample_contact.id,
        line_items=items,
        tax_rate="5.00",
        discount_amount="10.00",
    )

    # Expected line totals: 75.00, 100.00, 200.00
    line_totals = sorted(Decimal(str(li["total"])) for li in data["line_items"])
    assert line_totals == sorted([Decimal("75.00"), Decimal("100.00"), Decimal("200.00")])

    # Verify each line: total == qty * unit_price
    for li in data["line_items"]:
        expected = (Decimal(str(li["quantity"])) * Decimal(str(li["unit_price"]))).quantize(
            Decimal("0.01")
        )
        assert Decimal(str(li["total"])) == expected, f"Line '{li['description']}' total mismatch"

    # Subtotal = 75 + 100 + 200 = 375.00
    assert Decimal(str(data["subtotal"])) == Decimal("375.00")
    # Tax = 5% of 375 = 18.75
    assert Decimal(str(data["tax_amount"])) == Decimal("18.75")
    # Total = 375 + 18.75 - 10 = 383.75
    assert Decimal(str(data["total"])) == Decimal("383.75")


# =========================================================================
# 3. Read, list, search, filter by status
# =========================================================================


@pytest.mark.high
async def test_get_invoice(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """GET single invoice by ID returns full data."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]

    resp = await client.get(
        f"/api/invoices/{invoice_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == invoice_id
    assert data["invoice_number"] == created["invoice_number"]
    assert len(data["line_items"]) >= 1


@pytest.mark.high
async def test_list_invoices(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """GET list returns created invoices and supports pagination envelope."""
    await _create_invoice(client, admin_user, sample_contact.id)

    resp = await client.get("/api/invoices", headers=auth_header(admin_user))
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert len(body["data"]) >= 1


@pytest.mark.high
async def test_list_invoices_search(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Search by invoice number."""
    created = await _create_invoice(
        client, admin_user, sample_contact.id, notes="unique-search-term-xyz"
    )
    inv_number = created["invoice_number"]

    resp = await client.get(
        f"/api/invoices?search={inv_number}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert any(r["invoice_number"] == inv_number for r in results)


@pytest.mark.high
async def test_list_invoices_filter_status(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Filter by status=draft returns only draft invoices."""
    await _create_invoice(client, admin_user, sample_contact.id)

    resp = await client.get(
        "/api/invoices?status=draft", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    for inv in resp.json()["data"]:
        assert inv["status"] == "draft"


@pytest.mark.high
async def test_list_invoices_filter_contact_id(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Filter by contact_id returns only invoices for that contact."""
    await _create_invoice(client, admin_user, sample_contact.id)
    contact_id = str(sample_contact.id)

    resp = await client.get(
        f"/api/invoices?contact_id={contact_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    for inv in resp.json()["data"]:
        assert inv["contact_id"] == contact_id


# =========================================================================
# 4. Update invoice — change line items, verify recalculation
# =========================================================================


async def test_update_invoice_recalculates(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """PUT with new line items triggers subtotal/tax/total recalculation."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]

    new_items = [
        {"description": "New Service", "quantity": "5", "unit_price": "300.00"},
    ]
    resp = await client.put(
        f"/api/invoices/{invoice_id}",
        json={"line_items": new_items},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    # New subtotal: 5 * 300 = 1500.00
    assert Decimal(str(data["subtotal"])) == Decimal("1500.00")
    # Tax rate was 10% from creation => tax = 150.00
    assert Decimal(str(data["tax_amount"])) == Decimal("150.00")
    # Total = 1500 + 150 = 1650.00
    assert Decimal(str(data["total"])) == Decimal("1650.00")
    assert len(data["line_items"]) == 1
    assert data["line_items"][0]["description"] == "New Service"


# =========================================================================
# 5. Delete invoice — admin only, viewer/accountant get 403
# =========================================================================


async def test_delete_invoice_admin(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Admin can delete an invoice."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]

    resp = await client.delete(
        f"/api/invoices/{invoice_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    # Verify gone
    resp2 = await client.get(
        f"/api/invoices/{invoice_id}", headers=auth_header(admin_user)
    )
    assert resp2.status_code == 404


async def test_delete_invoice_accountant_forbidden(
    client: AsyncClient,
    admin_user: User,
    accountant_user: User,
    sample_contact,
):
    """Accountant cannot delete invoices (403)."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]

    resp = await client.delete(
        f"/api/invoices/{invoice_id}", headers=auth_header(accountant_user)
    )
    assert resp.status_code == 403


async def test_delete_invoice_viewer_forbidden(
    client: AsyncClient,
    admin_user: User,
    viewer_user: User,
    sample_contact,
):
    """Viewer cannot delete invoices (403)."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]

    resp = await client.delete(
        f"/api/invoices/{invoice_id}", headers=auth_header(viewer_user)
    )
    assert resp.status_code == 403


# =========================================================================
# 6. Sequential invoice numbering
# =========================================================================


async def test_invoice_sequential_numbering(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Creating two invoices yields sequential invoice numbers."""
    first = await _create_invoice(client, admin_user, sample_contact.id)
    second = await _create_invoice(client, admin_user, sample_contact.id)

    # Both should start with INV- and the second should have a higher sequence
    assert first["invoice_number"].startswith("INV-")
    assert second["invoice_number"].startswith("INV-")
    first_num = int(first["invoice_number"].split("-")[1])
    second_num = int(second["invoice_number"].split("-")[1])
    assert second_num > first_num


# =========================================================================
# 7. Status transitions: draft -> sent
# =========================================================================


@pytest.mark.critical
async def test_send_invoice_draft_to_sent(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /send transitions a draft invoice to sent."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    assert created["status"] == "draft"

    resp = await client.post(
        f"/api/invoices/{created['id']}/send", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "sent"


@pytest.mark.critical
async def test_send_already_sent_invoice_fails(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Cannot send an invoice that is not in draft status."""
    created = await _create_invoice(client, admin_user, sample_contact.id)

    # Send once
    resp = await client.post(
        f"/api/invoices/{created['id']}/send", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200

    # Attempt to send again — should fail (already sent)
    resp2 = await client.post(
        f"/api/invoices/{created['id']}/send", headers=auth_header(admin_user)
    )
    assert resp2.status_code in (400, 422)


# =========================================================================
# 8. Record payment — partial payment => PARTIALLY_PAID
# =========================================================================


@pytest.mark.high
async def test_partial_payment_status(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Recording a payment less than total sets status to partially_paid."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]
    total = Decimal(str(created["total"]))

    # Pay half
    half = (total / 2).quantize(Decimal("0.01"))
    payment_body = {
        "amount": str(half),
        "date": _TODAY.isoformat(),
        "payment_method": "bank_transfer",
        "reference": "CHK-001",
        "notes": "Partial payment",
    }
    resp = await client.post(
        f"/api/invoices/{invoice_id}/payments",
        json=payment_body,
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    payment_data = resp.json()["data"]
    assert Decimal(str(payment_data["amount"])) == half

    # Verify invoice status
    inv_resp = await client.get(
        f"/api/invoices/{invoice_id}", headers=auth_header(admin_user)
    )
    assert inv_resp.json()["data"]["status"] == "partially_paid"


# =========================================================================
# 9. Record full payment => PAID
# =========================================================================


@pytest.mark.critical
async def test_full_payment_marks_paid(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Recording a payment equal to total sets status to paid."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]
    total = str(created["total"])

    resp = await client.post(
        f"/api/invoices/{invoice_id}/payments",
        json={"amount": total, "date": _TODAY.isoformat()},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201

    inv_resp = await client.get(
        f"/api/invoices/{invoice_id}", headers=auth_header(admin_user)
    )
    assert inv_resp.json()["data"]["status"] == "paid"


@pytest.mark.critical
async def test_cumulative_payments_mark_paid(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Two partial payments totalling >= invoice total results in paid status."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]
    total = Decimal(str(created["total"]))
    half = (total / 2).quantize(Decimal("0.01"))
    remainder = total - half

    # First payment
    resp1 = await client.post(
        f"/api/invoices/{invoice_id}/payments",
        json={"amount": str(half), "date": _TODAY.isoformat()},
        headers=auth_header(admin_user),
    )
    assert resp1.status_code == 201

    # Second payment
    resp2 = await client.post(
        f"/api/invoices/{invoice_id}/payments",
        json={"amount": str(remainder), "date": _TODAY.isoformat()},
        headers=auth_header(admin_user),
    )
    assert resp2.status_code == 201

    inv_resp = await client.get(
        f"/api/invoices/{invoice_id}", headers=auth_header(admin_user)
    )
    assert inv_resp.json()["data"]["status"] == "paid"


# =========================================================================
# 10. Cannot record payment with zero or negative amount (schema validation)
# =========================================================================


@pytest.mark.high
async def test_payment_zero_amount_rejected(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Payment amount must be > 0 (schema validation)."""
    created = await _create_invoice(client, admin_user, sample_contact.id)

    resp = await client.post(
        f"/api/invoices/{created['id']}/payments",
        json={"amount": "0", "date": _TODAY.isoformat()},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422


@pytest.mark.high
async def test_payment_negative_amount_rejected(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Payment with negative amount is rejected at schema level."""
    created = await _create_invoice(client, admin_user, sample_contact.id)

    resp = await client.post(
        f"/api/invoices/{created['id']}/payments",
        json={"amount": "-100.00", "date": _TODAY.isoformat()},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422


# =========================================================================
# 11. Unauthenticated access returns 401
# =========================================================================


@pytest.mark.critical
async def test_list_invoices_unauthenticated(client: AsyncClient):
    """GET /api/invoices without auth token returns 401."""
    resp = await client.get("/api/invoices")
    assert resp.status_code == 401


@pytest.mark.critical
async def test_create_invoice_unauthenticated(
    client: AsyncClient,
    sample_contact,
):
    """POST /api/invoices without auth token returns 401."""
    payload = _invoice_payload(sample_contact.id)
    resp = await client.post("/api/invoices", json=payload)
    assert resp.status_code == 401


@pytest.mark.critical
async def test_get_invoice_unauthenticated(client: AsyncClient):
    """GET /api/invoices/{id} without auth returns 401."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/invoices/{fake_id}")
    assert resp.status_code == 401


@pytest.mark.critical
async def test_delete_invoice_unauthenticated(client: AsyncClient):
    """DELETE /api/invoices/{id} without auth returns 401."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api/invoices/{fake_id}")
    assert resp.status_code == 401


@pytest.mark.critical
async def test_send_invoice_unauthenticated(client: AsyncClient):
    """POST /api/invoices/{id}/send without auth returns 401."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/invoices/{fake_id}/send")
    assert resp.status_code == 401


@pytest.mark.critical
async def test_record_payment_unauthenticated(client: AsyncClient):
    """POST /api/invoices/{id}/payments without auth returns 401."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/invoices/{fake_id}/payments",
        json={"amount": "100", "date": _TODAY.isoformat()},
    )
    assert resp.status_code == 401


# =========================================================================
# 11b. Viewer cannot create or update invoices (role restriction)
# =========================================================================


async def test_create_invoice_viewer_forbidden(
    client: AsyncClient,
    viewer_user: User,
    sample_contact,
):
    """Viewer role cannot create invoices."""
    payload = _invoice_payload(sample_contact.id)
    resp = await client.post(
        "/api/invoices", json=payload, headers=auth_header(viewer_user)
    )
    assert resp.status_code == 403


async def test_update_invoice_viewer_forbidden(
    client: AsyncClient,
    admin_user: User,
    viewer_user: User,
    sample_contact,
):
    """Viewer role cannot update invoices."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    resp = await client.put(
        f"/api/invoices/{created['id']}",
        json={"notes": "changed"},
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403


# =========================================================================
# 11c. Accountant CAN create invoices
# =========================================================================


async def test_accountant_can_create_invoice(
    client: AsyncClient,
    accountant_user: User,
    sample_contact,
):
    """Accountant role can create invoices."""
    payload = _invoice_payload(sample_contact.id)
    resp = await client.post(
        "/api/invoices", json=payload, headers=auth_header(accountant_user)
    )
    assert resp.status_code == 201


# =========================================================================
# 12. Stats endpoint returns correct structure
# =========================================================================


@pytest.mark.normal
async def test_invoice_stats(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """GET /api/invoices/stats returns expected keys."""
    # Create an invoice first so there is data
    await _create_invoice(client, admin_user, sample_contact.id)

    resp = await client.get(
        "/api/invoices/stats", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    stats = resp.json()["data"]
    assert "total_outstanding" in stats
    assert "total_overdue" in stats
    assert "total_paid_this_month" in stats
    assert "invoice_count" in stats
    assert stats["invoice_count"] >= 1


@pytest.mark.normal
async def test_invoice_stats_unauthenticated(client: AsyncClient):
    """Stats endpoint requires authentication."""
    resp = await client.get("/api/invoices/stats")
    assert resp.status_code == 401


# =========================================================================
# 13. Create estimate, convert to invoice — verify data transferred
# =========================================================================


@pytest.mark.high
async def test_estimate_convert_to_invoice(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """POST /api/estimates/{id}/convert-to-invoice creates an invoice with matching data."""
    # Create an estimate
    est_payload = _estimate_payload(sample_contact.id)
    est_resp = await client.post(
        "/api/estimates", json=est_payload, headers=auth_header(admin_user)
    )
    assert est_resp.status_code == 201
    estimate = est_resp.json()["data"]
    estimate_id = estimate["id"]

    # Convert to invoice
    conv_resp = await client.post(
        f"/api/estimates/{estimate_id}/convert-to-invoice",
        headers=auth_header(admin_user),
    )
    assert conv_resp.status_code == 201
    invoice = conv_resp.json()["data"]

    # Verify data transferred correctly
    assert invoice["contact_id"] == str(sample_contact.id)
    assert Decimal(str(invoice["subtotal"])) == Decimal(str(estimate["subtotal"]))
    assert Decimal(str(invoice["total"])) == Decimal(str(estimate["total"]))
    assert invoice["currency"] == estimate["currency"]
    assert invoice["notes"] == estimate["notes"]
    assert invoice["invoice_number"].startswith("INV-")
    # Line items count should match
    assert len(invoice["line_items"]) == len(estimate["line_items"])

    # Verify estimate is now marked as converted
    est_get = await client.get(
        f"/api/estimates/{estimate_id}", headers=auth_header(admin_user)
    )
    assert est_get.status_code == 200
    est_data = est_get.json()["data"]
    assert est_data["status"] == "converted"
    assert est_data["converted_invoice_id"] == invoice["id"]


# =========================================================================
# 14. Double-convert estimate blocked
# =========================================================================


@pytest.mark.high
async def test_estimate_double_convert_blocked(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Converting an already-converted estimate returns an error."""
    # Create and convert an estimate
    est_payload = _estimate_payload(sample_contact.id)
    est_resp = await client.post(
        "/api/estimates", json=est_payload, headers=auth_header(admin_user)
    )
    assert est_resp.status_code == 201
    estimate_id = est_resp.json()["data"]["id"]

    # First conversion succeeds
    resp1 = await client.post(
        f"/api/estimates/{estimate_id}/convert-to-invoice",
        headers=auth_header(admin_user),
    )
    assert resp1.status_code == 201

    # Second conversion must fail
    resp2 = await client.post(
        f"/api/estimates/{estimate_id}/convert-to-invoice",
        headers=auth_header(admin_user),
    )
    assert resp2.status_code in (400, 409, 422)


# =========================================================================
# Additional edge-case tests
# =========================================================================


async def test_create_invoice_no_line_items_rejected(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Invoice with empty line_items list is rejected (min_length=1)."""
    payload = _invoice_payload(sample_contact.id, line_items=[])
    resp = await client.post(
        "/api/invoices", json=payload, headers=auth_header(admin_user)
    )
    assert resp.status_code == 422


async def test_create_invoice_no_tax(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Invoice with tax_rate=null results in total == subtotal - discount."""
    data = await _create_invoice(
        client,
        admin_user,
        sample_contact.id,
        tax_rate=None,
        discount_amount="50.00",
    )
    subtotal = Decimal(str(data["subtotal"]))
    total = Decimal(str(data["total"]))
    assert data["tax_amount"] is None
    assert total == subtotal - Decimal("50.00")


async def test_get_nonexistent_invoice(
    client: AsyncClient,
    admin_user: User,
):
    """GET /api/invoices/{nonexistent_id} returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/invoices/{fake_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 404


async def test_delete_nonexistent_invoice(
    client: AsyncClient,
    admin_user: User,
):
    """DELETE /api/invoices/{nonexistent_id} returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/api/invoices/{fake_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 404


async def test_send_nonexistent_invoice(
    client: AsyncClient,
    admin_user: User,
):
    """POST /api/invoices/{nonexistent_id}/send returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/invoices/{fake_id}/send", headers=auth_header(admin_user)
    )
    assert resp.status_code == 404


async def test_record_payment_nonexistent_invoice(
    client: AsyncClient,
    admin_user: User,
):
    """POST /api/invoices/{nonexistent_id}/payments returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/invoices/{fake_id}/payments",
        json={"amount": "100.00", "date": _TODAY.isoformat()},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 404


async def test_update_invoice_notes(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """PUT with only notes field updates notes without touching totals."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]
    original_total = created["total"]

    resp = await client.put(
        f"/api/invoices/{invoice_id}",
        json={"notes": "Updated notes for test"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["notes"] == "Updated notes for test"
    # Total should remain the same since we did not change line items
    assert str(data["total"]) == str(original_total)


async def test_list_invoices_filter_date_range(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Filter invoices by date_from and date_to."""
    await _create_invoice(client, admin_user, sample_contact.id)

    yesterday = (_TODAY - timedelta(days=1)).isoformat()
    tomorrow = (_TODAY + timedelta(days=1)).isoformat()

    resp = await client.get(
        f"/api/invoices?date_from={yesterday}&date_to={tomorrow}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


async def test_payment_with_all_fields(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Payment with all optional fields present is accepted."""
    created = await _create_invoice(client, admin_user, sample_contact.id)

    resp = await client.post(
        f"/api/invoices/{created['id']}/payments",
        json={
            "amount": "100.00",
            "date": _TODAY.isoformat(),
            "payment_method": "credit_card",
            "reference": "REF-12345",
            "notes": "First installment",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["payment_method"] == "credit_card"
    assert data["reference"] == "REF-12345"
    assert data["notes"] == "First installment"
    assert data["recorded_by"] == str(admin_user.id)


async def test_invoice_response_includes_payments_list(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """GET invoice after payment shows the payment in payments list."""
    created = await _create_invoice(client, admin_user, sample_contact.id)
    invoice_id = created["id"]

    await client.post(
        f"/api/invoices/{invoice_id}/payments",
        json={"amount": "500.00", "date": _TODAY.isoformat()},
        headers=auth_header(admin_user),
    )

    resp = await client.get(
        f"/api/invoices/{invoice_id}", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["payments"]) == 1
    assert Decimal(str(data["payments"][0]["amount"])) == Decimal("500.00")


async def test_convert_rejected_estimate_blocked(
    client: AsyncClient,
    admin_user: User,
    sample_contact,
):
    """Cannot convert a rejected estimate to an invoice."""
    est_payload = _estimate_payload(sample_contact.id)
    est_resp = await client.post(
        "/api/estimates", json=est_payload, headers=auth_header(admin_user)
    )
    assert est_resp.status_code == 201
    estimate_id = est_resp.json()["data"]["id"]

    # Mark as rejected via update
    rej_resp = await client.put(
        f"/api/estimates/{estimate_id}",
        json={"status": "rejected"},
        headers=auth_header(admin_user),
    )
    assert rej_resp.status_code == 200

    # Attempt conversion
    conv_resp = await client.post(
        f"/api/estimates/{estimate_id}/convert-to-invoice",
        headers=auth_header(admin_user),
    )
    assert conv_resp.status_code in (400, 409, 422)
