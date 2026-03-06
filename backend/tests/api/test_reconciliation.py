"""Tests for the /api/reconciliation endpoints (receipt-to-transaction matching)."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense, ExpenseStatus, PaymentMethod
from app.auth.models import User
from app.cashbook.models import CashbookEntry, EntryType
from tests.conftest import auth_header

TODAY = date.today()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def expense_and_transaction(db: AsyncSession, admin_user: User, sample_payment_account):
    """Create a matching expense and cashbook entry ($100, vendor=Acme, same day)."""
    expense = Expense(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        vendor_name="Acme",
        description="Acme supplies",
        amount=Decimal("100.00"),
        currency="USD",
        date=TODAY,
        status=ExpenseStatus.APPROVED,
        payment_method=PaymentMethod.BANK_TRANSFER,
    )
    entry = CashbookEntry(
        id=uuid.uuid4(),
        account_id=sample_payment_account.id,
        entry_type=EntryType.EXPENSE,
        date=TODAY,
        description="Acme payment",
        total_amount=Decimal("100.00"),
        user_id=admin_user.id,
    )
    db.add_all([expense, entry])
    await db.commit()
    await db.refresh(expense)
    await db.refresh(entry)
    return expense, entry


# ---------------------------------------------------------------------------
# 1. find-matches creates a match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_matches_creates_match(
    client: AsyncClient,
    admin_user: User,
    expense_and_transaction,
):
    """Exact amount, same vendor, same date -- should produce a high-confidence match."""
    headers = auth_header(admin_user)

    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) >= 1

    match = data[0]
    assert match["status"] == "pending"
    assert match["match_confidence"] >= 50


# ---------------------------------------------------------------------------
# 2. amount within 10% threshold matches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amount_within_threshold(
    client: AsyncClient,
    admin_user: User,
    db: AsyncSession,
    sample_payment_account,
):
    """Expense $100 vs transaction $109 (9% diff) should still match."""
    headers = auth_header(admin_user)

    expense = Expense(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        vendor_name="BetaCo",
        description="Beta supplies",
        amount=Decimal("100.00"),
        currency="USD",
        date=TODAY,
        status=ExpenseStatus.APPROVED,
        payment_method=PaymentMethod.BANK_TRANSFER,
    )
    entry = CashbookEntry(
        id=uuid.uuid4(),
        account_id=sample_payment_account.id,
        entry_type=EntryType.EXPENSE,
        date=TODAY,
        description="BetaCo payment",
        total_amount=Decimal("109.00"),
        user_id=admin_user.id,
    )
    db.add_all([expense, entry])
    await db.commit()

    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) >= 1
    assert any(str(expense.id) == m["receipt_id"] for m in data)


# ---------------------------------------------------------------------------
# 3. amount outside 10% threshold does NOT match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amount_outside_threshold(
    client: AsyncClient,
    admin_user: User,
    db: AsyncSession,
    sample_payment_account,
):
    """Expense $100 vs transaction $115 (15% diff) should NOT match."""
    headers = auth_header(admin_user)

    expense = Expense(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        vendor_name="GammaCo",
        description="Gamma purchase",
        amount=Decimal("100.00"),
        currency="USD",
        date=TODAY,
        status=ExpenseStatus.APPROVED,
        payment_method=PaymentMethod.BANK_TRANSFER,
    )
    entry = CashbookEntry(
        id=uuid.uuid4(),
        account_id=sample_payment_account.id,
        entry_type=EntryType.EXPENSE,
        date=TODAY,
        description="GammaCo payment",
        total_amount=Decimal("115.00"),
        user_id=admin_user.id,
    )
    db.add_all([expense, entry])
    await db.commit()

    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    matched_receipt_ids = [m["receipt_id"] for m in data]
    assert str(expense.id) not in matched_receipt_ids


# ---------------------------------------------------------------------------
# 4. dates within 7 days should match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_date_within_7_days(
    client: AsyncClient,
    admin_user: User,
    db: AsyncSession,
    sample_payment_account,
):
    """Same amount, dates 5 days apart -- should match."""
    headers = auth_header(admin_user)

    expense = Expense(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        vendor_name="DeltaCo",
        description="Delta order",
        amount=Decimal("200.00"),
        currency="USD",
        date=TODAY,
        status=ExpenseStatus.APPROVED,
        payment_method=PaymentMethod.BANK_TRANSFER,
    )
    entry = CashbookEntry(
        id=uuid.uuid4(),
        account_id=sample_payment_account.id,
        entry_type=EntryType.EXPENSE,
        date=TODAY - timedelta(days=5),
        description="DeltaCo payment",
        total_amount=Decimal("200.00"),
        user_id=admin_user.id,
    )
    db.add_all([expense, entry])
    await db.commit()

    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert any(str(expense.id) == m["receipt_id"] for m in data)


# ---------------------------------------------------------------------------
# 5. dates outside 7 days should NOT match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_date_outside_7_days(
    client: AsyncClient,
    admin_user: User,
    db: AsyncSession,
    sample_payment_account,
):
    """Same amount, dates 10 days apart -- should NOT match."""
    headers = auth_header(admin_user)

    expense = Expense(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        vendor_name="EpsilonCo",
        description="Epsilon order",
        amount=Decimal("300.00"),
        currency="USD",
        date=TODAY,
        status=ExpenseStatus.APPROVED,
        payment_method=PaymentMethod.BANK_TRANSFER,
    )
    entry = CashbookEntry(
        id=uuid.uuid4(),
        account_id=sample_payment_account.id,
        entry_type=EntryType.EXPENSE,
        date=TODAY - timedelta(days=10),
        description="EpsilonCo payment",
        total_amount=Decimal("300.00"),
        user_id=admin_user.id,
    )
    db.add_all([expense, entry])
    await db.commit()

    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    matched_receipt_ids = [m["receipt_id"] for m in data]
    assert str(expense.id) not in matched_receipt_ids


# ---------------------------------------------------------------------------
# 6. confirm a match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_match(
    client: AsyncClient,
    admin_user: User,
    expense_and_transaction,
):
    """Find a match, confirm it, verify status becomes confirmed."""
    headers = auth_header(admin_user)

    # Create the match
    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    match_id = resp.json()["data"][0]["id"]

    # Confirm it
    resp = await client.post(
        f"/api/reconciliation/matches/{match_id}/confirm",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "confirmed"
    assert resp.json()["data"]["confirmed_by"] is not None


# ---------------------------------------------------------------------------
# 7. reject a match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_match(
    client: AsyncClient,
    admin_user: User,
    expense_and_transaction,
):
    """Find a match, reject it, verify status becomes rejected."""
    headers = auth_header(admin_user)

    # Create the match
    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    match_id = resp.json()["data"][0]["id"]

    # Reject it
    resp = await client.post(
        f"/api/reconciliation/matches/{match_id}/reject",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "rejected"


# ---------------------------------------------------------------------------
# 8. manual match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_match(
    client: AsyncClient,
    admin_user: User,
    expense_and_transaction,
):
    """Create a manual match -- should be immediately confirmed with 100% confidence."""
    headers = auth_header(admin_user)
    expense, entry = expense_and_transaction

    resp = await client.post(
        "/api/reconciliation/manual-match",
        json={
            "receipt_id": str(expense.id),
            "transaction_id": str(entry.id),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "confirmed"
    assert data["match_confidence"] == 100.0
    assert data["confirmed_by"] is not None


# ---------------------------------------------------------------------------
# 9. confirmed matches excluded from future find-matches runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmed_excluded_from_future_matches(
    client: AsyncClient,
    admin_user: User,
    expense_and_transaction,
):
    """After confirming a match, a second find-matches run should not duplicate it."""
    headers = auth_header(admin_user)

    # First run -- creates a match
    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    match_id = resp.json()["data"][0]["id"]

    # Confirm the match
    resp = await client.post(
        f"/api/reconciliation/matches/{match_id}/confirm",
        headers=headers,
    )
    assert resp.status_code == 200

    # Second run -- should not find new matches for the same pair
    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == 0


# ---------------------------------------------------------------------------
# 10. summary returns correct counts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_returns_counts(
    client: AsyncClient,
    admin_user: User,
    expense_and_transaction,
):
    """Verify the summary endpoint reports correct counts after creating data."""
    headers = auth_header(admin_user)

    # Before matching -- both items unmatched
    resp = await client.get("/api/reconciliation/summary", headers=headers)
    assert resp.status_code == 200, resp.text
    summary = resp.json()["data"]
    assert summary["unmatched_receipts"] >= 1
    assert summary["unmatched_transactions"] >= 1

    # Run find-matches to create a pending match
    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 200

    # After matching -- should have pending match, no unmatched
    resp = await client.get("/api/reconciliation/summary", headers=headers)
    assert resp.status_code == 200, resp.text
    summary = resp.json()["data"]
    assert summary["pending_matches"] >= 1
    assert summary["unmatched_receipts"] == 0
    assert summary["unmatched_transactions"] == 0


# ---------------------------------------------------------------------------
# 11. unauthenticated returns 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_401(client: AsyncClient):
    """All reconciliation endpoints require authentication."""
    fake_id = str(uuid.uuid4())

    endpoints = [
        ("GET", "/api/reconciliation/matches"),
        ("POST", "/api/reconciliation/find-matches"),
        ("POST", f"/api/reconciliation/matches/{fake_id}/confirm"),
        ("POST", f"/api/reconciliation/matches/{fake_id}/reject"),
        ("POST", "/api/reconciliation/manual-match"),
        ("GET", "/api/reconciliation/unmatched-receipts"),
        ("GET", "/api/reconciliation/unmatched-transactions"),
        ("GET", "/api/reconciliation/summary"),
    ]

    for method, path in endpoints:
        resp = await client.request(method, path)
        assert resp.status_code in (401, 403, 422), (
            f"{method} {path} returned {resp.status_code}, expected 401/403"
        )


# ---------------------------------------------------------------------------
# 12. viewer cannot run find-matches (role restriction)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_viewer_cannot_find_matches(
    client: AsyncClient,
    viewer_user: User,
):
    """Viewer role is not in [ACCOUNTANT, ADMIN] -- should get 403."""
    headers = auth_header(viewer_user)

    resp = await client.post(
        "/api/reconciliation/find-matches",
        json={"date_from": None, "date_to": None},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
