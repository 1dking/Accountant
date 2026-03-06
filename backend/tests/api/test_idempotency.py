"""Idempotency-key tests for all financial POST endpoints.

Verifies that the ``Idempotency-Key`` header prevents duplicate record creation
while remaining backwards-compatible when the header is omitted.
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header

pytestmark = pytest.mark.critical


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoice_payload(contact_id: uuid.UUID) -> dict:
    return {
        "contact_id": str(contact_id),
        "issue_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "tax_rate": "10.00",
        "discount_amount": "0.00",
        "currency": "USD",
        "line_items": [{"description": "Test", "quantity": "1", "unit_price": "100.00"}],
    }


def _expense_payload() -> dict:
    return {
        "vendor_name": "Test",
        "description": "Test",
        "amount": "50.00",
        "currency": "USD",
        "date": date.today().isoformat(),
    }


def _cashbook_payload(account_id: uuid.UUID) -> dict:
    return {
        "account_id": str(account_id),
        "entry_type": "income",
        "date": date.today().isoformat(),
        "description": "Test",
        "total_amount": "100.00",
    }


def _income_payload() -> dict:
    return {
        "category": "service",
        "description": "Test",
        "amount": "100.00",
        "currency": "USD",
        "date": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# 1. Invoice idempotency
# ---------------------------------------------------------------------------


async def test_invoice_idempotency(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Sending the same invoice create request twice with the same key creates only one invoice."""
    key = f"inv-{uuid.uuid4()}"
    headers = {**auth_header(admin_user), "Idempotency-Key": key}
    payload = _invoice_payload(sample_contact.id)

    r1 = await client.post("/api/invoices", json=payload, headers=headers)
    assert r1.status_code == 201
    invoice_id_1 = r1.json()["data"]["id"]

    r2 = await client.post("/api/invoices", json=payload, headers=headers)
    # Second call should succeed (cached) with the same data
    assert r2.status_code in (200, 201)
    invoice_id_2 = r2.json()["data"]["id"]

    assert invoice_id_1 == invoice_id_2, "Second request should return cached invoice, not create a new one"

    # Verify only one invoice exists by listing
    r_list = await client.get("/api/invoices", headers=auth_header(admin_user))
    assert r_list.status_code == 200
    invoices = r_list.json()["data"]
    matching = [inv for inv in invoices if inv["id"] == invoice_id_1]
    assert len(matching) == 1


# ---------------------------------------------------------------------------
# 2. Payment idempotency
# ---------------------------------------------------------------------------


async def test_payment_idempotency(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Recording the same payment twice with the same key creates only one payment."""
    # First create an invoice
    inv_r = await client.post(
        "/api/invoices",
        json=_invoice_payload(sample_contact.id),
        headers=auth_header(admin_user),
    )
    assert inv_r.status_code == 201
    invoice_id = inv_r.json()["data"]["id"]

    # Now record payment with idempotency key
    key = f"pay-{uuid.uuid4()}"
    headers = {**auth_header(admin_user), "Idempotency-Key": key}
    payment_data = {
        "amount": "50.00",
        "date": date.today().isoformat(),
        "payment_method": "bank_transfer",
    }

    r1 = await client.post(
        f"/api/invoices/{invoice_id}/payments", json=payment_data, headers=headers
    )
    assert r1.status_code == 201
    payment_id_1 = r1.json()["data"]["id"]

    r2 = await client.post(
        f"/api/invoices/{invoice_id}/payments", json=payment_data, headers=headers
    )
    assert r2.status_code in (200, 201)
    payment_id_2 = r2.json()["data"]["id"]

    assert payment_id_1 == payment_id_2, "Second request should return cached payment"

    # Verify only one payment recorded on the invoice
    inv_detail = await client.get(
        f"/api/invoices/{invoice_id}", headers=auth_header(admin_user)
    )
    assert inv_detail.status_code == 200
    payments = inv_detail.json()["data"]["payments"]
    assert len(payments) == 1


# ---------------------------------------------------------------------------
# 3. Expense idempotency
# ---------------------------------------------------------------------------


async def test_expense_idempotency(
    client: AsyncClient,
    admin_user,
):
    """Sending the same expense create request twice with the same key creates only one expense."""
    key = f"exp-{uuid.uuid4()}"
    headers = {**auth_header(admin_user), "Idempotency-Key": key}
    payload = _expense_payload()

    r1 = await client.post("/api/accounting/expenses", json=payload, headers=headers)
    assert r1.status_code == 201
    expense_id_1 = r1.json()["data"]["id"]

    r2 = await client.post("/api/accounting/expenses", json=payload, headers=headers)
    assert r2.status_code in (200, 201)
    expense_id_2 = r2.json()["data"]["id"]

    assert expense_id_1 == expense_id_2, "Second request should return cached expense"


# ---------------------------------------------------------------------------
# 4. Cashbook idempotency
# ---------------------------------------------------------------------------


async def test_cashbook_idempotency(
    client: AsyncClient,
    admin_user,
    sample_payment_account,
):
    """Sending the same cashbook entry twice with the same key creates only one entry."""
    key = f"cb-{uuid.uuid4()}"
    headers = {**auth_header(admin_user), "Idempotency-Key": key}
    payload = _cashbook_payload(sample_payment_account.id)

    r1 = await client.post("/api/cashbook/entries", json=payload, headers=headers)
    assert r1.status_code == 201
    entry_id_1 = r1.json()["data"]["id"]

    r2 = await client.post("/api/cashbook/entries", json=payload, headers=headers)
    assert r2.status_code in (200, 201)
    entry_id_2 = r2.json()["data"]["id"]

    assert entry_id_1 == entry_id_2, "Second request should return cached cashbook entry"


# ---------------------------------------------------------------------------
# 5. Income idempotency
# ---------------------------------------------------------------------------


async def test_income_idempotency(
    client: AsyncClient,
    admin_user,
):
    """Sending the same income create request twice with the same key creates only one entry."""
    key = f"inc-{uuid.uuid4()}"
    headers = {**auth_header(admin_user), "Idempotency-Key": key}
    payload = _income_payload()

    r1 = await client.post("/api/income", json=payload, headers=headers)
    assert r1.status_code == 201
    income_id_1 = r1.json()["data"]["id"]

    r2 = await client.post("/api/income", json=payload, headers=headers)
    assert r2.status_code in (200, 201)
    income_id_2 = r2.json()["data"]["id"]

    assert income_id_1 == income_id_2, "Second request should return cached income entry"


# ---------------------------------------------------------------------------
# 6. Different keys create different records
# ---------------------------------------------------------------------------


async def test_different_keys_create_different_records(
    client: AsyncClient,
    admin_user,
    sample_payment_account,
):
    """Sending the same data with different Idempotency-Key values creates two records."""
    payload = _cashbook_payload(sample_payment_account.id)

    key_a = f"cb-a-{uuid.uuid4()}"
    key_b = f"cb-b-{uuid.uuid4()}"

    r1 = await client.post(
        "/api/cashbook/entries",
        json=payload,
        headers={**auth_header(admin_user), "Idempotency-Key": key_a},
    )
    assert r1.status_code == 201
    entry_id_a = r1.json()["data"]["id"]

    r2 = await client.post(
        "/api/cashbook/entries",
        json=payload,
        headers={**auth_header(admin_user), "Idempotency-Key": key_b},
    )
    assert r2.status_code == 201
    entry_id_b = r2.json()["data"]["id"]

    assert entry_id_a != entry_id_b, "Different keys should create separate records"


# ---------------------------------------------------------------------------
# 7. No key = normal behaviour (backwards compatible)
# ---------------------------------------------------------------------------


async def test_no_key_creates_normally(
    client: AsyncClient,
    admin_user,
    sample_payment_account,
):
    """Sending requests without Idempotency-Key creates records normally each time."""
    payload = _cashbook_payload(sample_payment_account.id)
    headers = auth_header(admin_user)  # no Idempotency-Key

    r1 = await client.post("/api/cashbook/entries", json=payload, headers=headers)
    assert r1.status_code == 201
    entry_id_1 = r1.json()["data"]["id"]

    r2 = await client.post("/api/cashbook/entries", json=payload, headers=headers)
    assert r2.status_code == 201
    entry_id_2 = r2.json()["data"]["id"]

    assert entry_id_1 != entry_id_2, "Without idempotency key, each request should create a new record"


# ---------------------------------------------------------------------------
# 8. Key is scoped to endpoint
# ---------------------------------------------------------------------------


async def test_key_scoped_to_endpoint(
    client: AsyncClient,
    admin_user,
    sample_payment_account,
):
    """The same Idempotency-Key used on different endpoints creates one record per endpoint."""
    shared_key = f"shared-{uuid.uuid4()}"

    # Create a cashbook entry
    cb_headers = {**auth_header(admin_user), "Idempotency-Key": shared_key}
    r_cb = await client.post(
        "/api/cashbook/entries",
        json=_cashbook_payload(sample_payment_account.id),
        headers=cb_headers,
    )
    assert r_cb.status_code == 201
    cb_id = r_cb.json()["data"]["id"]

    # Create an expense with the same key
    exp_headers = {**auth_header(admin_user), "Idempotency-Key": shared_key}
    r_exp = await client.post(
        "/api/accounting/expenses",
        json=_expense_payload(),
        headers=exp_headers,
    )
    assert r_exp.status_code == 201
    exp_id = r_exp.json()["data"]["id"]

    # Both should have been created (not blocked by the shared key)
    assert cb_id != exp_id, "Same key on different endpoints should create separate records"

    # Replaying the cashbook call should still return the cached cashbook entry
    r_cb_replay = await client.post(
        "/api/cashbook/entries",
        json=_cashbook_payload(sample_payment_account.id),
        headers=cb_headers,
    )
    assert r_cb_replay.status_code in (200, 201)
    assert r_cb_replay.json()["data"]["id"] == cb_id

    # Replaying the expense call should still return the cached expense
    r_exp_replay = await client.post(
        "/api/accounting/expenses",
        json=_expense_payload(),
        headers=exp_headers,
    )
    assert r_exp_replay.status_code in (200, 201)
    assert r_exp_replay.json()["data"]["id"] == exp_id
