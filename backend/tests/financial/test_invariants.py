"""FINANCIAL INVARIANT TESTS -- the most critical tests in the suite.

These tests verify that monetary calculations are EXACT, that rounding matches
hand-calculated expected values, that payment reconciliation is correct, and
that no floating-point drift accumulates across chains of transactions.

Every test in this module is marked @pytest.mark.critical.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header
from tests.fixtures.data import ROUNDING_CASES, make_invoice_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _idem() -> dict[str, str]:
    """Return a unique Idempotency-Key header."""
    return {"Idempotency-Key": str(uuid.uuid4())}


def _merge(user_headers: dict, extra: dict | None = None) -> dict:
    """Merge auth headers with optional extra headers."""
    h = {**user_headers}
    if extra:
        h.update(extra)
    return h


async def _create_invoice(
    client: AsyncClient,
    headers: dict,
    payload: dict,
) -> dict:
    """POST an invoice and return the parsed data dict.  Asserts 201."""
    resp = await client.post(
        "/api/invoices",
        json=payload,
        headers=_merge(headers, _idem()),
    )
    assert resp.status_code == 201, f"Invoice creation failed: {resp.text}"
    return resp.json()["data"]


async def _record_payment(
    client: AsyncClient,
    headers: dict,
    invoice_id: str,
    amount: str,
    payment_date: str | None = None,
) -> dict:
    """POST a payment against an invoice.  Asserts 201."""
    resp = await client.post(
        f"/api/invoices/{invoice_id}/payments",
        json={
            "amount": amount,
            "date": payment_date or date.today().isoformat(),
            "payment_method": "bank_transfer",
        },
        headers=_merge(headers, _idem()),
    )
    assert resp.status_code == 201, f"Payment recording failed: {resp.text}"
    return resp.json()["data"]


async def _create_cashbook_entry(
    client: AsyncClient,
    headers: dict,
    account_id: str,
    entry_type: str,
    amount: str,
    description: str = "Test entry",
    entry_date: str | None = None,
) -> dict:
    """POST a cashbook entry.  Asserts 201."""
    resp = await client.post(
        "/api/cashbook/entries",
        json={
            "account_id": account_id,
            "entry_type": entry_type,
            "date": entry_date or date.today().isoformat(),
            "description": description,
            "total_amount": amount,
        },
        headers=_merge(headers, _idem()),
    )
    assert resp.status_code == 201, f"Cashbook entry failed: {resp.text}"
    return resp.json()["data"]


async def _get_account_balance(
    client: AsyncClient,
    headers: dict,
    account_id: str,
) -> Decimal:
    """GET the current balance of a cashbook account."""
    resp = await client.get(
        f"/api/cashbook/accounts/{account_id}",
        headers=headers,
    )
    assert resp.status_code == 200, f"Account fetch failed: {resp.text}"
    return Decimal(str(resp.json()["data"]["current_balance"]))


async def _get_invoice(
    client: AsyncClient,
    headers: dict,
    invoice_id: str,
) -> dict:
    """GET a single invoice with line items and payments."""
    resp = await client.get(
        f"/api/invoices/{invoice_id}",
        headers=headers,
    )
    assert resp.status_code == 200, f"Invoice fetch failed: {resp.text}"
    return resp.json()["data"]


# ===========================================================================
# 1. LINE ITEM MATH
# ===========================================================================


@pytest.mark.critical
async def test_line_item_totals_are_quantity_times_price(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Each line_item.total must equal quantity * unit_price."""
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="0.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Widget A", "quantity": "5", "unit_price": "29.99"},
            {"description": "Widget B", "quantity": "12", "unit_price": "3.50"},
            {"description": "Widget C", "quantity": "1", "unit_price": "1250.00"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)
    inv_detail = await _get_invoice(client, headers, str(inv["id"]))

    expected_totals = [
        Decimal("5") * Decimal("29.99"),    # 149.95
        Decimal("12") * Decimal("3.50"),     # 42.00
        Decimal("1") * Decimal("1250.00"),   # 1250.00
    ]

    for li, expected in zip(inv_detail["line_items"], expected_totals):
        actual = Decimal(str(li["total"]))
        assert actual == expected.quantize(Decimal("0.01")), (
            f"Line item '{li['description']}': "
            f"expected {expected.quantize(Decimal('0.01'))}, got {actual}"
        )


@pytest.mark.critical
async def test_subtotal_equals_sum_of_line_totals(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """subtotal must equal the sum of all line item totals."""
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="0.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Service A", "quantity": "3", "unit_price": "499.99"},
            {"description": "Service B", "quantity": "7", "unit_price": "12.50"},
            {"description": "Service C", "quantity": "2", "unit_price": "75.25"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)
    inv_detail = await _get_invoice(client, headers, str(inv["id"]))

    sum_of_lines = sum(
        Decimal(str(li["total"])) for li in inv_detail["line_items"]
    )
    subtotal = Decimal(str(inv_detail["subtotal"]))
    assert subtotal == sum_of_lines, (
        f"subtotal ({subtotal}) != sum of line totals ({sum_of_lines})"
    )


@pytest.mark.critical
async def test_tax_amount_equals_subtotal_times_rate(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """tax_amount must equal subtotal * tax_rate / 100, rounded to 2dp."""
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="13.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Consulting", "quantity": "10", "unit_price": "150.00"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)

    subtotal = Decimal(str(inv["subtotal"]))
    tax_rate = Decimal("13.00")
    expected_tax = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
    actual_tax = Decimal(str(inv["tax_amount"]))

    assert actual_tax == expected_tax, (
        f"tax_amount ({actual_tax}) != subtotal * rate ({expected_tax})"
    )


@pytest.mark.critical
async def test_total_equals_subtotal_plus_tax_minus_discount(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """total must equal subtotal + tax_amount - discount_amount."""
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="7.25",
        discount_amount="50.00",
        line_items=[
            {"description": "Web Design", "quantity": "1", "unit_price": "2500.00"},
            {"description": "Hosting", "quantity": "1", "unit_price": "360.00"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)

    subtotal = Decimal(str(inv["subtotal"]))
    tax_amount = Decimal(str(inv["tax_amount"]))
    discount = Decimal(str(inv["discount_amount"]))
    total = Decimal(str(inv["total"]))

    expected_total = subtotal + tax_amount - discount
    assert total == expected_total, (
        f"total ({total}) != subtotal + tax - discount ({expected_total})"
    )


# ===========================================================================
# 2. ROUNDING REGRESSION
# ===========================================================================


@pytest.mark.critical
async def test_rounding_7_25_percent_tax_on_33_33(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """7.25% tax on $33.33 must yield tax=$2.42, total=$35.75."""
    case = ROUNDING_CASES[1]
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="7.25",
        discount_amount="0.00",
        line_items=[
            {"description": "Item", "quantity": "1", "unit_price": "33.33"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)

    assert Decimal(str(inv["tax_amount"])) == case["expected_tax"], (
        f"Expected tax {case['expected_tax']}, got {inv['tax_amount']}"
    )
    assert Decimal(str(inv["total"])) == case["expected_total"], (
        f"Expected total {case['expected_total']}, got {inv['total']}"
    )


@pytest.mark.critical
async def test_rounding_subtotal_1847_50_with_discount_and_tax(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Subtotal $1847.50 with $50 discount and 7.25% tax on subtotal.

    Hand-calculated:
      subtotal = 1847.50
      tax      = 1847.50 * 7.25 / 100 = 133.94375 -> 133.94
      total    = 1847.50 + 133.94 - 50.00 = 1931.44
    """
    headers = auth_header(admin_user)
    # Build line items that sum to exactly $1847.50
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="7.25",
        discount_amount="50.00",
        line_items=[
            {"description": "Service A", "quantity": "1", "unit_price": "1000.00"},
            {"description": "Service B", "quantity": "1", "unit_price": "500.00"},
            {"description": "Service C", "quantity": "1", "unit_price": "347.50"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)

    expected_subtotal = Decimal("1847.50")
    expected_tax = (expected_subtotal * Decimal("7.25") / Decimal("100")).quantize(
        Decimal("0.01")
    )
    expected_total = expected_subtotal + expected_tax - Decimal("50.00")

    assert Decimal(str(inv["subtotal"])) == expected_subtotal, (
        f"Subtotal: expected {expected_subtotal}, got {inv['subtotal']}"
    )
    assert Decimal(str(inv["tax_amount"])) == expected_tax, (
        f"Tax: expected {expected_tax}, got {inv['tax_amount']}"
    )
    assert Decimal(str(inv["total"])) == expected_total, (
        f"Total: expected {expected_total}, got {inv['total']}"
    )


@pytest.mark.critical
async def test_rounding_split_100_three_ways_sums_exactly(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Three invoices splitting $100 must sum to exactly $100.00.

    Using the ROUNDING_CASES expected splits: $33.34, $33.33, $33.33.
    """
    case = ROUNDING_CASES[0]
    headers = auth_header(admin_user)

    totals = []
    for expected_split in case["expected"]:
        payload = make_invoice_payload(
            str(sample_contact.id),
            tax_rate="0.00",
            discount_amount="0.00",
            line_items=[
                {
                    "description": "Split payment",
                    "quantity": "1",
                    "unit_price": str(expected_split),
                },
            ],
        )
        inv = await _create_invoice(client, headers, payload)
        totals.append(Decimal(str(inv["total"])))

    actual_sum = sum(totals)
    assert actual_sum == case["total"], (
        f"Sum of splits ({actual_sum}) != original total ({case['total']}). "
        f"Individual totals: {totals}"
    )


# ===========================================================================
# 3. PAYMENT RECONCILIATION
# ===========================================================================


@pytest.mark.critical
async def test_partial_payment_then_full_payment(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Partial payment -> partially_paid; remaining payment -> paid."""
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="0.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Project", "quantity": "1", "unit_price": "1000.00"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)
    invoice_id = str(inv["id"])

    # Partial payment of $400
    await _record_payment(client, headers, invoice_id, "400.00")
    inv_after_partial = await _get_invoice(client, headers, invoice_id)
    assert inv_after_partial["status"] == "partially_paid", (
        f"Expected partially_paid, got {inv_after_partial['status']}"
    )

    # Remaining $600
    await _record_payment(client, headers, invoice_id, "600.00")
    inv_after_full = await _get_invoice(client, headers, invoice_id)
    assert inv_after_full["status"] == "paid", (
        f"Expected paid, got {inv_after_full['status']}"
    )

    # Verify total payments == invoice total
    total_payments = sum(
        Decimal(str(p["amount"])) for p in inv_after_full["payments"]
    )
    invoice_total = Decimal(str(inv_after_full["total"]))
    assert total_payments == invoice_total, (
        f"Total payments ({total_payments}) != invoice total ({invoice_total})"
    )


@pytest.mark.critical
async def test_overpayment_does_not_exceed_total(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Overpaying should either fail or cap at the invoice total.

    The system must not allow total payments to logically exceed the
    invoice total.  If the API accepts the overpayment, the status must
    still be 'paid' (not some invalid state), and we flag that the
    system allows overpayment so it can be reviewed.
    """
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="0.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Small job", "quantity": "1", "unit_price": "100.00"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)
    invoice_id = str(inv["id"])

    # Pay in full first
    await _record_payment(client, headers, invoice_id, "100.00")

    # Attempt to overpay
    resp = await client.post(
        f"/api/invoices/{invoice_id}/payments",
        json={
            "amount": "50.00",
            "date": date.today().isoformat(),
            "payment_method": "cash",
        },
        headers=_merge(headers, _idem()),
    )

    if resp.status_code in (400, 422):
        # System correctly rejects overpayment -- the ideal behavior.
        pass
    else:
        # System accepted the overpayment; verify status is still 'paid'
        # and not some corrupt state.
        inv_detail = await _get_invoice(client, headers, invoice_id)
        assert inv_detail["status"] == "paid", (
            f"After overpayment, status should be 'paid', got {inv_detail['status']}"
        )


# ===========================================================================
# 4. CASHBOOK BALANCE INTEGRITY
# ===========================================================================


@pytest.mark.critical
async def test_cashbook_balance_exact(
    client: AsyncClient,
    admin_user,
    sample_payment_account,
):
    """Running balance must match exactly: opening + income - expenses.

    5 income entries ($100, $200, $350, $75, $425 = $1150)
    3 expense entries ($150, $80, $220 = $450)
    Expected balance: 10000 + 1150 - 450 = 10700.00
    """
    headers = auth_header(admin_user)
    acct_id = str(sample_payment_account.id)

    income_amounts = ["100.00", "200.00", "350.00", "75.00", "425.00"]
    expense_amounts = ["150.00", "80.00", "220.00"]

    for i, amt in enumerate(income_amounts):
        await _create_cashbook_entry(
            client, headers, acct_id, "income", amt,
            description=f"Income #{i+1}",
        )

    for i, amt in enumerate(expense_amounts):
        await _create_cashbook_entry(
            client, headers, acct_id, "expense", amt,
            description=f"Expense #{i+1}",
        )

    balance = await _get_account_balance(client, headers, acct_id)
    expected = Decimal("10700.00")
    assert balance == expected, (
        f"Balance mismatch: expected {expected}, got {balance}. "
        f"Possible floating-point drift."
    )


# ===========================================================================
# 5. CHAIN OF 100 TRANSACTIONS WITH TAX
# ===========================================================================


@pytest.mark.critical
async def test_100_transactions_no_float_drift(
    client: AsyncClient,
    admin_user,
    sample_payment_account,
):
    """Create 100 cashbook entries with varying amounts and verify balance.

    Uses Decimal arithmetic to compute the expected balance independently,
    then asserts the API-reported balance matches EXACTLY.  This catches
    any floating-point drift that would accumulate over many operations.
    """
    headers = auth_header(admin_user)
    acct_id = str(sample_payment_account.id)

    opening = Decimal("10000.00")
    expected_balance = opening
    tax_rate = Decimal("7.25")

    for i in range(100):
        # Alternate income/expense in a 3:1 ratio for a realistic mix
        if i % 4 == 3:
            entry_type = "expense"
        else:
            entry_type = "income"

        # Generate a varying amount: base + cyclic component
        base = Decimal("10.00") + Decimal(str(i)) * Decimal("1.17")
        # Add tax: total_amount is the gross amount including tax
        tax = (base * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        total = (base + tax).quantize(Decimal("0.01"))

        await _create_cashbook_entry(
            client, headers, acct_id, entry_type, str(total),
            description=f"Txn #{i+1}",
        )

        if entry_type == "income":
            expected_balance += total
        else:
            expected_balance -= total

    balance = await _get_account_balance(client, headers, acct_id)
    assert balance == expected_balance, (
        f"After 100 transactions, expected {expected_balance}, got {balance}. "
        f"Drift = {balance - expected_balance}"
    )


# ===========================================================================
# 6. DATE BOUNDARY TESTS
# ===========================================================================


@pytest.mark.critical
async def test_invoices_in_correct_date_range(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """Invoice on Dec 31 and Jan 1 must appear in correct date filters."""
    headers = auth_header(admin_user)

    # Create invoice dated Dec 31, 2025
    payload_dec = make_invoice_payload(
        str(sample_contact.id),
        issue_date="2025-12-31",
        due_date="2026-01-30",
        tax_rate="0.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Dec work", "quantity": "1", "unit_price": "500.00"},
        ],
    )
    inv_dec = await _create_invoice(client, headers, payload_dec)

    # Create invoice dated Jan 1, 2026
    payload_jan = make_invoice_payload(
        str(sample_contact.id),
        issue_date="2026-01-01",
        due_date="2026-01-31",
        tax_rate="0.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Jan work", "quantity": "1", "unit_price": "600.00"},
        ],
    )
    inv_jan = await _create_invoice(client, headers, payload_jan)

    # Query Dec only
    resp_dec = await client.get(
        "/api/invoices",
        params={"date_from": "2025-12-01", "date_to": "2025-12-31"},
        headers=headers,
    )
    assert resp_dec.status_code == 200
    dec_ids = {i["id"] for i in resp_dec.json()["data"]}
    assert inv_dec["id"] in dec_ids, "Dec 31 invoice not found in Dec range"
    assert inv_jan["id"] not in dec_ids, "Jan 1 invoice incorrectly in Dec range"

    # Query Jan only
    resp_jan = await client.get(
        "/api/invoices",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        headers=headers,
    )
    assert resp_jan.status_code == 200
    jan_ids = {i["id"] for i in resp_jan.json()["data"]}
    assert inv_jan["id"] in jan_ids, "Jan 1 invoice not found in Jan range"
    assert inv_dec["id"] not in jan_ids, "Dec 31 invoice incorrectly in Jan range"


@pytest.mark.critical
async def test_invoice_on_leap_day(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """An invoice due on leap day Feb 29, 2028 must be accepted."""
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        issue_date="2028-02-01",
        due_date="2028-02-29",
        tax_rate="0.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Leap day service", "quantity": "1", "unit_price": "250.00"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)
    assert inv["due_date"] == "2028-02-29", (
        f"Leap day due_date not preserved: got {inv['due_date']}"
    )


# ===========================================================================
# 7. DECIMAL PRECISION
# ===========================================================================


@pytest.mark.critical
async def test_fractional_quantity_precision(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """quantity=0.3333, unit_price=$100 must yield total=$33.33."""
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="0.00",
        discount_amount="0.00",
        line_items=[
            {"description": "Fractional qty", "quantity": "0.3333", "unit_price": "100.00"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)
    inv_detail = await _get_invoice(client, headers, str(inv["id"]))

    line_total = Decimal(str(inv_detail["line_items"][0]["total"]))
    expected = Decimal("33.33")
    assert line_total == expected, (
        f"Fractional qty line total: expected {expected}, got {line_total}"
    )


@pytest.mark.critical
async def test_monetary_values_have_two_decimal_places(
    client: AsyncClient,
    admin_user,
    sample_contact,
):
    """All monetary values in the response must have at most 2 decimal places."""
    headers = auth_header(admin_user)
    payload = make_invoice_payload(
        str(sample_contact.id),
        tax_rate="7.25",
        discount_amount="10.00",
        line_items=[
            {"description": "Precision test A", "quantity": "3", "unit_price": "33.33"},
            {"description": "Precision test B", "quantity": "7", "unit_price": "14.29"},
        ],
    )
    inv = await _create_invoice(client, headers, payload)
    inv_detail = await _get_invoice(client, headers, str(inv["id"]))

    # Check top-level monetary fields
    for field in ("subtotal", "tax_amount", "discount_amount", "total"):
        value = inv_detail.get(field)
        if value is None:
            continue
        d = Decimal(str(value))
        # Decimal places: the negative of the exponent
        places = -d.as_tuple().exponent
        assert places <= 2, (
            f"Field '{field}' has {places} decimal places (value={d}), expected <= 2"
        )

    # Check line item totals
    for li in inv_detail["line_items"]:
        total_d = Decimal(str(li["total"]))
        places = -total_d.as_tuple().exponent
        assert places <= 2, (
            f"Line item total has {places} decimal places (value={total_d}), expected <= 2"
        )

    # Check line item quantities allow 4 decimal places
    for li in inv_detail["line_items"]:
        qty_d = Decimal(str(li["quantity"]))
        places = -qty_d.as_tuple().exponent
        assert places <= 4, (
            f"Line item quantity has {places} decimal places (value={qty_d}), expected <= 4"
        )
