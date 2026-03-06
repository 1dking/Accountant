"""Concurrency / load tests using asyncio.gather.

These tests fire many simultaneous requests to verify the system handles
concurrent writes correctly: no duplicates, correct balances, proper
sequential numbering, and no errors on mixed read/write workloads.

NOTE: Tests that require true concurrency (parallel writes to the same
table) are skipped when running on SQLite because SQLite serialises all
writes through a single connection, making race-condition testing meaningless.
"""

import asyncio
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header

_skip_sqlite = pytest.mark.skip(
    reason="SQLite serialises writes through a single connection; true concurrency requires PostgreSQL"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cashbook_income_payload(account_id: uuid.UUID, amount: str = "100.00") -> dict:
    return {
        "account_id": str(account_id),
        "entry_type": "income",
        "date": date.today().isoformat(),
        "description": "Concurrent income entry",
        "total_amount": amount,
    }


def _invoice_payload(contact_id: uuid.UUID, index: int = 0) -> dict:
    return {
        "contact_id": str(contact_id),
        "issue_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "tax_rate": "0.00",
        "discount_amount": "0.00",
        "currency": "USD",
        "line_items": [
            {
                "description": f"Service item {index}",
                "quantity": "1",
                "unit_price": "100.00",
            }
        ],
    }


def _payment_payload(amount: str = "200.00") -> dict:
    return {
        "amount": amount,
        "date": date.today().isoformat(),
        "payment_method": "bank_transfer",
    }


# ---------------------------------------------------------------------------
# 1. 50 concurrent cashbook entries
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_50_concurrent_cashbook_entries(
    client: AsyncClient,
    admin_user,
    sample_payment_account,
):
    """Create 50 cashbook income entries simultaneously and verify totals."""
    n = 50
    amount_each = "100.00"
    headers = auth_header(admin_user)
    payload = _cashbook_income_payload(sample_payment_account.id, amount_each)

    async def _create_entry():
        return await client.post("/api/cashbook/entries", json=payload, headers=headers)

    results = await asyncio.gather(*[_create_entry() for _ in range(n)])

    # All requests should succeed with 201
    created_ids = []
    for r in results:
        assert r.status_code == 201, f"Expected 201 but got {r.status_code}: {r.text}"
        created_ids.append(r.json()["data"]["id"])

    # No duplicate IDs
    assert len(set(created_ids)) == n, f"Expected {n} unique entries, got {len(set(created_ids))}"

    # Verify balance: opening_balance + sum(all income amounts)
    account_r = await client.get(
        f"/api/cashbook/accounts/{sample_payment_account.id}",
        headers=headers,
    )
    assert account_r.status_code == 200
    current_balance = Decimal(str(account_r.json()["data"]["current_balance"]))
    expected_balance = Decimal("10000.00") + Decimal(amount_each) * n
    assert current_balance == expected_balance, (
        f"Expected balance {expected_balance}, got {current_balance}"
    )


# ---------------------------------------------------------------------------
# 2. 20 concurrent invoice creates
# ---------------------------------------------------------------------------


@_skip_sqlite
@pytest.mark.high
async def test_20_concurrent_invoice_creates(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Create 20 invoices simultaneously and verify sequential numbering with no gaps."""
    n = 20
    headers = auth_header(admin_user)

    async def _create_invoice(idx: int):
        return await client.post(
            "/api/invoices",
            json=_invoice_payload(sample_contact.id, idx),
            headers=headers,
        )

    results = await asyncio.gather(*[_create_invoice(i) for i in range(n)])

    # All requests should succeed
    invoice_ids = []
    invoice_numbers = []
    for r in results:
        assert r.status_code == 201, f"Expected 201 but got {r.status_code}: {r.text}"
        data = r.json()["data"]
        invoice_ids.append(data["id"])
        invoice_numbers.append(data["invoice_number"])

    # All unique IDs
    assert len(set(invoice_ids)) == n, f"Expected {n} unique invoices, got {len(set(invoice_ids))}"

    # All unique invoice numbers
    assert len(set(invoice_numbers)) == n, (
        f"Expected {n} unique invoice numbers, got {len(set(invoice_numbers))}"
    )

    # Extract numeric parts and verify contiguous sequence (no gaps)
    nums = sorted(
        int(m.group(1))
        for num_str in invoice_numbers
        if (m := re.search(r"(\d+)$", num_str))
    )
    assert len(nums) == n
    for i in range(1, len(nums)):
        assert nums[i] == nums[i - 1] + 1, (
            f"Gap in invoice numbers: {nums[i - 1]} -> {nums[i]}"
        )


# ---------------------------------------------------------------------------
# 3. Concurrent payments on same invoice
# ---------------------------------------------------------------------------


@_skip_sqlite
@pytest.mark.high
async def test_concurrent_payments_on_same_invoice(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Send 5 concurrent $200 payments on a $1000 invoice; verify no overpayment."""
    headers = auth_header(admin_user)

    # Create a $1000 invoice
    inv_payload = {
        "contact_id": str(sample_contact.id),
        "issue_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "tax_rate": "0.00",
        "discount_amount": "0.00",
        "currency": "USD",
        "line_items": [
            {"description": "Big project", "quantity": "1", "unit_price": "1000.00"}
        ],
    }
    inv_r = await client.post("/api/invoices", json=inv_payload, headers=headers)
    assert inv_r.status_code == 201
    invoice_id = inv_r.json()["data"]["id"]
    assert Decimal(str(inv_r.json()["data"]["total"])) == Decimal("1000.00")

    # Send 5 concurrent $200 payments
    payment_count = 5

    async def _pay():
        return await client.post(
            f"/api/invoices/{invoice_id}/payments",
            json=_payment_payload("200.00"),
            headers=headers,
        )

    results = await asyncio.gather(*[_pay() for _ in range(payment_count)])

    # All requests should succeed with 201
    payment_ids = []
    for r in results:
        assert r.status_code == 201, f"Expected 201 but got {r.status_code}: {r.text}"
        payment_ids.append(r.json()["data"]["id"])

    assert len(set(payment_ids)) == payment_count, "All payments should be unique"

    # Fetch the invoice and verify total paid
    inv_detail = await client.get(f"/api/invoices/{invoice_id}", headers=headers)
    assert inv_detail.status_code == 200
    inv_data = inv_detail.json()["data"]
    payments = inv_data["payments"]
    total_paid = sum(Decimal(str(p["amount"])) for p in payments)

    assert total_paid == Decimal("1000.00"), (
        f"Total paid should be $1000.00, got {total_paid}"
    )
    assert inv_data["status"] == "paid", (
        f"Invoice should be 'paid' after full payment, got '{inv_data['status']}'"
    )


# ---------------------------------------------------------------------------
# 4. Concurrent reads while writing
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_concurrent_reads_while_writing(
    client: AsyncClient,
    admin_user,
    sample_payment_account,
):
    """Simultaneously create entries and read the list endpoint; verify no errors."""
    headers = auth_header(admin_user)
    payload = _cashbook_income_payload(sample_payment_account.id, "50.00")

    write_count = 10
    read_count = 10

    async def _write():
        return await client.post("/api/cashbook/entries", json=payload, headers=headers)

    async def _read():
        return await client.get(
            f"/api/cashbook/entries?account_id={sample_payment_account.id}",
            headers=headers,
        )

    # Mix writes and reads in parallel
    tasks = [_write() for _ in range(write_count)] + [_read() for _ in range(read_count)]
    results = await asyncio.gather(*tasks)

    write_results = results[:write_count]
    read_results = results[write_count:]

    # All writes should succeed
    for r in write_results:
        assert r.status_code == 201, f"Write failed with {r.status_code}: {r.text}"

    # All reads should succeed (200) and return valid JSON
    for r in read_results:
        assert r.status_code == 200, f"Read failed with {r.status_code}: {r.text}"
        body = r.json()
        assert "data" in body, "Response should contain 'data' key"
        assert isinstance(body["data"], list), "Entries data should be a list"
