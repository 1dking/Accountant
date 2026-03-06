"""Tests for the Gmail inbox/import/delete functionality.

These tests cover the enhanced Gmail integration:
- Paginated results listing
- Delete single & bulk scan results
- Email parsing / auto-categorization
- Full import flow (attachment + expense/income creation)
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.integrations.gmail.models import GmailAccount, GmailScanResult
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def gmail_account(db: AsyncSession, admin_user: User) -> GmailAccount:
    account = GmailAccount(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        email="test@gmail.com",
        encrypted_access_token="enc_token",
        encrypted_refresh_token="enc_refresh",
        scopes="gmail.readonly",
        is_active=True,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@pytest_asyncio.fixture()
async def scan_results(
    db: AsyncSession, gmail_account: GmailAccount
) -> list[GmailScanResult]:
    results = []
    for i in range(5):
        sr = GmailScanResult(
            id=uuid.uuid4(),
            gmail_account_id=gmail_account.id,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            subject=f"Invoice #{i + 1} from Vendor{i}",
            sender=f"vendor{i}@example.com",
            date=datetime(2025, 6, 15 + i, tzinfo=timezone.utc),
            snippet=f"Here is invoice {i + 1}",
            body_text=f"Total: ${(i + 1) * 100}.00\nVendor{i} Inc.",
            has_attachments=i < 3,
            is_processed=i >= 3,
        )
        db.add(sr)
        results.append(sr)
    await db.commit()
    for sr in results:
        await db.refresh(sr)
    return results


# =========================================================================
# 1. Paginated results listing
# =========================================================================


@pytest.mark.high
@pytest.mark.asyncio
async def test_list_results_paginated(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
):
    """GET /integrations/gmail/results returns paginated results."""
    resp = await client.get(
        "/api/integrations/gmail/results?page=1&page_size=3",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 3
    assert data["meta"]["total"] == 5
    assert data["meta"]["page"] == 1
    assert data["meta"]["total_pages"] == 2


@pytest.mark.normal
@pytest.mark.asyncio
async def test_list_results_filter_status(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
):
    """GET /integrations/gmail/results?is_processed=false returns only pending."""
    resp = await client.get(
        "/api/integrations/gmail/results?is_processed=false",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["is_processed"] is False for r in data["data"])
    assert data["meta"]["total"] == 3


@pytest.mark.normal
@pytest.mark.asyncio
async def test_list_results_search(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
):
    """GET /integrations/gmail/results?search=Invoice+%231 filters by subject text."""
    resp = await client.get(
        "/api/integrations/gmail/results?search=Invoice+%231",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] >= 1
    assert any("Invoice #1" in (r["subject"] or "") for r in data["data"])


# =========================================================================
# 2. Delete scan results
# =========================================================================


@pytest.mark.high
@pytest.mark.asyncio
async def test_delete_single_result(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
    db: AsyncSession,
):
    """DELETE /integrations/gmail/results/{id} removes it."""
    target_id = str(scan_results[0].id)
    resp = await client.delete(
        f"/api/integrations/gmail/results/{target_id}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    # Verify deleted
    result = await db.execute(
        select(GmailScanResult).where(GmailScanResult.id == scan_results[0].id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.high
@pytest.mark.asyncio
async def test_bulk_delete_results(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
    db: AsyncSession,
):
    """POST /integrations/gmail/results/bulk-delete removes multiple."""
    ids = [str(scan_results[0].id), str(scan_results[1].id)]
    resp = await client.post(
        "/api/integrations/gmail/results/bulk-delete",
        json={"result_ids": ids},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] == 2

    # Verify deleted
    result = await db.execute(select(GmailScanResult))
    remaining = result.scalars().all()
    assert len(remaining) == 3


@pytest.mark.normal
@pytest.mark.asyncio
async def test_delete_nonexistent_result(
    client: AsyncClient,
    admin_user: User,
    gmail_account: GmailAccount,
):
    """DELETE /integrations/gmail/results/{id} returns 404 for unknown id."""
    resp = await client.delete(
        f"/api/integrations/gmail/results/{uuid.uuid4()}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 404


@pytest.mark.normal
@pytest.mark.asyncio
async def test_delete_unauthenticated(
    client: AsyncClient,
    scan_results: list[GmailScanResult],
):
    """DELETE /integrations/gmail/results/{id} requires auth."""
    resp = await client.delete(
        f"/api/integrations/gmail/results/{scan_results[0].id}",
    )
    assert resp.status_code == 401


# =========================================================================
# 3. Email parsing / auto-categorization
# =========================================================================


@pytest.mark.high
@pytest.mark.asyncio
async def test_parse_email_extracts_data(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
):
    """GET /integrations/gmail/results/{id}/parse extracts vendor and amount."""
    target = scan_results[0]  # subject: "Invoice #1 from Vendor0", body: "Total: $100.00"
    resp = await client.get(
        f"/api/integrations/gmail/results/{target.id}/parse",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["vendor_name"] is not None
    assert data["amount"] == "100.00"
    assert data["record_type"] in ("expense", "income")


@pytest.mark.normal
@pytest.mark.asyncio
async def test_parse_email_suggests_category(
    client: AsyncClient,
    admin_user: User,
    db: AsyncSession,
    gmail_account: GmailAccount,
):
    """Parse correctly suggests category for known vendors like Anthropic."""
    sr = GmailScanResult(
        id=uuid.uuid4(),
        gmail_account_id=gmail_account.id,
        message_id=f"msg_anthropic_{uuid.uuid4().hex[:6]}",
        subject="Your Anthropic invoice",
        sender="billing@anthropic.com",
        date=datetime.now(timezone.utc),
        body_text="Invoice Total: $49.99",
        has_attachments=True,
        is_processed=False,
    )
    db.add(sr)
    await db.commit()

    resp = await client.get(
        f"/api/integrations/gmail/results/{sr.id}/parse",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["category_suggestion"] == "Software & SaaS"
    assert data["amount"] == "49.99"


# =========================================================================
# 4. Full import flow
# =========================================================================


@pytest.mark.critical
@pytest.mark.asyncio
async def test_import_full_creates_expense(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
    db: AsyncSession,
):
    """POST /integrations/gmail/results/{id}/import-full creates expense."""
    from app.accounting.models import Expense

    # Use a result without attachments to skip the Gmail API call
    target = scan_results[3]  # is_processed=True, but let's reset it
    target_id = target.id  # save before expire
    target.is_processed = False
    target.has_attachments = False
    await db.commit()

    resp = await client.post(
        f"/api/integrations/gmail/results/{target_id}/import-full",
        json={
            "record_type": "expense",
            "vendor_name": "TestVendor",
            "description": "Test expense from email",
            "amount": 250.00,
            "currency": "USD",
            "date": "2025-06-15",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["expense_id"] is not None
    assert data["document_id"] is None  # no attachment

    # Verify expense was created
    result = await db.execute(
        select(Expense).where(Expense.id == uuid.UUID(data["expense_id"]))
    )
    expense = result.scalar_one()
    expense_id = expense.id  # save before expire
    assert expense.vendor_name == "TestVendor"
    assert expense.amount == Decimal("250.00")
    assert str(expense.date) == "2025-06-15"

    # Verify scan result is now processed
    db.expire_all()
    result = await db.execute(
        select(GmailScanResult).where(GmailScanResult.id == target_id)
    )
    updated = result.scalar_one()
    assert updated.is_processed is True
    assert updated.matched_expense_id == expense_id


@pytest.mark.critical
@pytest.mark.asyncio
async def test_import_full_creates_income(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
    db: AsyncSession,
):
    """POST /integrations/gmail/results/{id}/import-full creates income record."""
    from app.income.models import Income

    target = scan_results[4]
    target_id = target.id  # save before expire
    target.is_processed = False
    target.has_attachments = False
    await db.commit()

    resp = await client.post(
        f"/api/integrations/gmail/results/{target_id}/import-full",
        json={
            "record_type": "income",
            "vendor_name": "Client",
            "description": "Payment received",
            "amount": 500.00,
            "date": "2025-06-20",
            "income_category": "service",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["income_id"] is not None

    # Verify income created
    result = await db.execute(
        select(Income).where(Income.id == uuid.UUID(data["income_id"]))
    )
    income = result.scalar_one()
    assert income.amount == Decimal("500.00")
    assert income.category.value == "service"


@pytest.mark.normal
@pytest.mark.asyncio
async def test_import_already_processed_fails(
    client: AsyncClient,
    admin_user: User,
    scan_results: list[GmailScanResult],
):
    """POST /integrations/gmail/results/{id}/import-full fails for processed emails."""
    target = scan_results[3]  # is_processed=True
    resp = await client.post(
        f"/api/integrations/gmail/results/{target.id}/import-full",
        json={"record_type": "expense", "amount": 100.00, "date": "2025-01-01"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422


@pytest.mark.normal
@pytest.mark.asyncio
async def test_import_unauthenticated(
    client: AsyncClient,
    scan_results: list[GmailScanResult],
):
    """POST /integrations/gmail/results/{id}/import-full requires auth."""
    resp = await client.post(
        f"/api/integrations/gmail/results/{scan_results[0].id}/import-full",
        json={"record_type": "expense"},
    )
    assert resp.status_code == 401


# =========================================================================
# 5. Viewer cannot delete or import
# =========================================================================


@pytest.mark.normal
@pytest.mark.asyncio
async def test_viewer_cannot_delete(
    client: AsyncClient,
    viewer_user: User,
    scan_results: list[GmailScanResult],
):
    """Viewer role cannot delete scan results."""
    resp = await client.delete(
        f"/api/integrations/gmail/results/{scan_results[0].id}",
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403


@pytest.mark.normal
@pytest.mark.asyncio
async def test_viewer_cannot_import(
    client: AsyncClient,
    viewer_user: User,
    scan_results: list[GmailScanResult],
):
    """Viewer role cannot import emails."""
    resp = await client.post(
        f"/api/integrations/gmail/results/{scan_results[0].id}/import-full",
        json={"record_type": "expense"},
        headers=auth_header(viewer_user),
    )
    assert resp.status_code == 403
