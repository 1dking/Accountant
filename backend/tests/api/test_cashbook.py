"""Tests for the /api/cashbook endpoints (accounts + entries + summary)."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.cashbook.models import PaymentAccount
from tests.conftest import auth_header

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
LAST_YEAR = TODAY - timedelta(days=365)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _account_payload(
    name: str = "Test Account",
    account_type: str = "bank",
    opening_balance: str = "5000.00",
    opening_balance_date: str | None = None,
) -> dict:
    return {
        "name": name,
        "account_type": account_type,
        "opening_balance": opening_balance,
        "opening_balance_date": opening_balance_date or LAST_YEAR.isoformat(),
    }


def _entry_payload(
    account_id: str,
    entry_type: str = "income",
    total_amount: str = "1000.00",
    description: str = "Test entry",
    entry_date: str | None = None,
) -> dict:
    return {
        "account_id": account_id,
        "entry_type": entry_type,
        "date": entry_date or TODAY.isoformat(),
        "description": description,
        "total_amount": total_amount,
    }


# ---------------------------------------------------------------------------
# 1. Create account -> create income entry -> verify balance
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_income_entry_increases_balance(
    client: AsyncClient, admin_user: User
):
    """Opening balance + income entry should equal correct current balance."""
    headers = auth_header(admin_user)

    # Create account with opening balance 5000
    resp = await client.post(
        "/api/cashbook/accounts",
        json=_account_payload(opening_balance="5000.00"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    account = resp.json()["data"]
    account_id = account["id"]
    assert Decimal(account["current_balance"]) == Decimal("5000.00")

    # Create income entry for 2000
    resp = await client.post(
        "/api/cashbook/entries",
        json=_entry_payload(account_id, entry_type="income", total_amount="2000.00"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    # Verify account balance is 5000 + 2000 = 7000
    resp = await client.get(
        f"/api/cashbook/accounts/{account_id}", headers=headers
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["data"]["current_balance"]) == Decimal("7000.00")


# ---------------------------------------------------------------------------
# 2. Income + expense entries -> verify running balance
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_income_and_expense_running_balance(
    client: AsyncClient, admin_user: User
):
    """Opening 10000 + income 3000 - expense 1500 = 11500."""
    headers = auth_header(admin_user)

    # Create account
    resp = await client.post(
        "/api/cashbook/accounts",
        json=_account_payload(name="Balance Check", opening_balance="10000.00"),
        headers=headers,
    )
    assert resp.status_code == 201
    account_id = resp.json()["data"]["id"]

    # Income entry
    resp = await client.post(
        "/api/cashbook/entries",
        json=_entry_payload(
            account_id,
            entry_type="income",
            total_amount="3000.00",
            description="Client payment",
        ),
        headers=headers,
    )
    assert resp.status_code == 201

    # Expense entry
    resp = await client.post(
        "/api/cashbook/entries",
        json=_entry_payload(
            account_id,
            entry_type="expense",
            total_amount="1500.00",
            description="Office rent",
        ),
        headers=headers,
    )
    assert resp.status_code == 201

    # Check balance: 10000 + 3000 - 1500 = 11500
    resp = await client.get(
        f"/api/cashbook/accounts/{account_id}", headers=headers
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["data"]["current_balance"]) == Decimal("11500.00")


# ---------------------------------------------------------------------------
# 3. Delete account WITH entries returns 409
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_delete_account_with_entries_returns_409(
    client: AsyncClient, admin_user: User
):
    """Cannot deactivate an account that still has cashbook entries."""
    headers = auth_header(admin_user)

    # Create account
    resp = await client.post(
        "/api/cashbook/accounts",
        json=_account_payload(name="Has Entries"),
        headers=headers,
    )
    assert resp.status_code == 201
    account_id = resp.json()["data"]["id"]

    # Add an entry
    resp = await client.post(
        "/api/cashbook/entries",
        json=_entry_payload(account_id, description="Blocking entry"),
        headers=headers,
    )
    assert resp.status_code == 201

    # Try to delete -- should be 409
    resp = await client.delete(
        f"/api/cashbook/accounts/{account_id}", headers=headers
    )
    assert resp.status_code == 409, resp.text
    error = resp.json()["error"]
    assert error["code"] == "CONFLICT"
    assert "transaction" in error["message"].lower()


# ---------------------------------------------------------------------------
# 4. Delete account WITHOUT entries succeeds (soft-delete)
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_delete_account_without_entries_succeeds(
    client: AsyncClient, admin_user: User
):
    """An account with no entries should be soft-deleted (deactivated)."""
    headers = auth_header(admin_user)

    # Create account
    resp = await client.post(
        "/api/cashbook/accounts",
        json=_account_payload(name="Empty Account"),
        headers=headers,
    )
    assert resp.status_code == 201
    account_id = resp.json()["data"]["id"]

    # Delete (deactivate)
    resp = await client.delete(
        f"/api/cashbook/accounts/{account_id}", headers=headers
    )
    assert resp.status_code == 200
    assert "deactivated" in resp.json()["data"]["message"].lower()

    # The account still exists but is_active=false; listing should exclude it
    resp = await client.get("/api/cashbook/accounts", headers=headers)
    assert resp.status_code == 200
    account_ids = [a["id"] for a in resp.json()["data"]]
    assert account_id not in account_ids


# ---------------------------------------------------------------------------
# 5. CRUD entries
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_crud_entries(client: AsyncClient, admin_user: User):
    """Create, read, list, update, and delete a cashbook entry."""
    headers = auth_header(admin_user)

    # Create account first
    resp = await client.post(
        "/api/cashbook/accounts",
        json=_account_payload(name="Entry CRUD Account"),
        headers=headers,
    )
    assert resp.status_code == 201
    account_id = resp.json()["data"]["id"]

    # CREATE entry
    entry_payload = _entry_payload(
        account_id,
        entry_type="expense",
        total_amount="250.00",
        description="Office supplies",
    )
    resp = await client.post(
        "/api/cashbook/entries", json=entry_payload, headers=headers
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()["data"]
    entry_id = entry["id"]
    assert entry["entry_type"] == "expense"
    assert Decimal(entry["total_amount"]) == Decimal("250.00")
    assert entry["description"] == "Office supplies"

    # READ entry
    resp = await client.get(
        f"/api/cashbook/entries/{entry_id}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == entry_id

    # LIST entries filtered by account
    resp = await client.get(
        "/api/cashbook/entries",
        params={"account_id": account_id},
        headers=headers,
    )
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()["data"]]
    assert entry_id in ids

    # UPDATE entry
    resp = await client.put(
        f"/api/cashbook/entries/{entry_id}",
        json={"description": "Updated supplies", "total_amount": "300.00"},
        headers=headers,
    )
    assert resp.status_code == 200
    updated = resp.json()["data"]
    assert updated["description"] == "Updated supplies"
    assert Decimal(updated["total_amount"]) == Decimal("300.00")

    # DELETE entry
    resp = await client.delete(
        f"/api/cashbook/entries/{entry_id}", headers=headers
    )
    assert resp.status_code == 200

    # Verify gone
    resp = await client.get(
        f"/api/cashbook/entries/{entry_id}", headers=headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. List entries with filters
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_list_entries_with_filters(
    client: AsyncClient, admin_user: User
):
    """Filter entries by entry_type, date_from, and date_to."""
    headers = auth_header(admin_user)

    # Create account
    resp = await client.post(
        "/api/cashbook/accounts",
        json=_account_payload(name="Filter Account"),
        headers=headers,
    )
    assert resp.status_code == 201
    account_id = resp.json()["data"]["id"]

    # Create income entry dated today
    resp = await client.post(
        "/api/cashbook/entries",
        json=_entry_payload(
            account_id,
            entry_type="income",
            total_amount="1000.00",
            description="Income today",
            entry_date=TODAY.isoformat(),
        ),
        headers=headers,
    )
    assert resp.status_code == 201

    # Create expense entry dated yesterday
    resp = await client.post(
        "/api/cashbook/entries",
        json=_entry_payload(
            account_id,
            entry_type="expense",
            total_amount="500.00",
            description="Expense yesterday",
            entry_date=YESTERDAY.isoformat(),
        ),
        headers=headers,
    )
    assert resp.status_code == 201

    # Filter by entry_type=income
    resp = await client.get(
        "/api/cashbook/entries",
        params={"account_id": account_id, "entry_type": "income"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(e["entry_type"] == "income" for e in data)
    assert len(data) >= 1

    # Filter by entry_type=expense
    resp = await client.get(
        "/api/cashbook/entries",
        params={"account_id": account_id, "entry_type": "expense"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(e["entry_type"] == "expense" for e in data)
    assert len(data) >= 1

    # Filter by date_from=today  (should exclude yesterday's expense)
    resp = await client.get(
        "/api/cashbook/entries",
        params={
            "account_id": account_id,
            "date_from": TODAY.isoformat(),
            "date_to": TODAY.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    descriptions = [e["description"] for e in data]
    assert "Income today" in descriptions
    assert "Expense yesterday" not in descriptions

    # Filter by date range covering yesterday only
    resp = await client.get(
        "/api/cashbook/entries",
        params={
            "account_id": account_id,
            "date_from": YESTERDAY.isoformat(),
            "date_to": YESTERDAY.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    descriptions = [e["description"] for e in data]
    assert "Expense yesterday" in descriptions
    assert "Income today" not in descriptions


# ---------------------------------------------------------------------------
# 7. Unauthenticated returns 401
# ---------------------------------------------------------------------------


@pytest.mark.critical
async def test_unauthenticated_returns_401(client: AsyncClient):
    """All cashbook endpoints require authentication."""
    fake_id = str(uuid.uuid4())

    endpoints = [
        ("GET", "/api/cashbook/accounts"),
        ("POST", "/api/cashbook/accounts"),
        ("GET", f"/api/cashbook/accounts/{fake_id}"),
        ("PUT", f"/api/cashbook/accounts/{fake_id}"),
        ("DELETE", f"/api/cashbook/accounts/{fake_id}"),
        ("GET", "/api/cashbook/entries"),
        ("POST", "/api/cashbook/entries"),
        ("GET", f"/api/cashbook/entries/{fake_id}"),
        ("PUT", f"/api/cashbook/entries/{fake_id}"),
        ("DELETE", f"/api/cashbook/entries/{fake_id}"),
    ]

    for method, path in endpoints:
        resp = await client.request(method, path)
        assert resp.status_code in (401, 403), (
            f"{method} {path} returned {resp.status_code}, expected 401 or 403"
        )


# ---------------------------------------------------------------------------
# 8. Negative balance handling
# ---------------------------------------------------------------------------


@pytest.mark.normal
async def test_negative_balance_handling(
    client: AsyncClient, admin_user: User
):
    """Expenses exceeding opening balance should result in a negative balance."""
    headers = auth_header(admin_user)

    # Create account with small opening balance
    resp = await client.post(
        "/api/cashbook/accounts",
        json=_account_payload(name="Low Balance", opening_balance="100.00"),
        headers=headers,
    )
    assert resp.status_code == 201
    account_id = resp.json()["data"]["id"]

    # Create expense greater than opening balance
    resp = await client.post(
        "/api/cashbook/entries",
        json=_entry_payload(
            account_id,
            entry_type="expense",
            total_amount="250.00",
            description="Overdrawn expense",
        ),
        headers=headers,
    )
    assert resp.status_code == 201

    # Balance should be negative: 100 - 250 = -150
    resp = await client.get(
        f"/api/cashbook/accounts/{account_id}", headers=headers
    )
    assert resp.status_code == 200
    balance = Decimal(resp.json()["data"]["current_balance"])
    assert balance == Decimal("-150.00")
    assert balance < 0
