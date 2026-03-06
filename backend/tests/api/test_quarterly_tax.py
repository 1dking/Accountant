"""Tests for the /api/reports quarterly-tax, year-over-year, and tax-deadline endpoints."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense, ExpenseStatus, PaymentMethod
from app.auth.models import User
from app.income.models import Income, IncomeCategory
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def seed_quarterly_data(db: AsyncSession, admin_user: User):
    """Create income and expenses across multiple quarters."""
    entries = [
        Income(
            id=uuid.uuid4(),
            created_by=admin_user.id,
            category=IncomeCategory.SERVICE,
            description="Q1 consulting",
            amount=Decimal("5000.00"),
            currency="USD",
            date=date(2026, 2, 15),
        ),
        Income(
            id=uuid.uuid4(),
            created_by=admin_user.id,
            category=IncomeCategory.PRODUCT,
            description="Q2 sales",
            amount=Decimal("3000.00"),
            currency="USD",
            date=date(2026, 5, 10),
        ),
        Expense(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            vendor_name="Office Supply",
            description="Q1 supplies",
            amount=Decimal("2000.00"),
            currency="USD",
            date=date(2026, 1, 20),
            status=ExpenseStatus.APPROVED,
            payment_method=PaymentMethod.BANK_TRANSFER,
        ),
        Expense(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            vendor_name="Tech Corp",
            description="Q2 software",
            amount=Decimal("1500.00"),
            currency="USD",
            date=date(2026, 4, 5),
            status=ExpenseStatus.APPROVED,
            payment_method=PaymentMethod.BANK_TRANSFER,
        ),
    ]
    db.add_all(entries)
    await db.commit()
    return entries


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quarterly_report_empty_year(client: AsyncClient, admin_user: User):
    """No data for the requested year — all quarters and annual totals are zero."""
    resp = await client.get(
        "/api/reports/tax-quarterly",
        params={"year": 2099, "tax_rate": 25.0},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert len(data["quarters"]) == 4
    for q in data["quarters"]:
        assert q["income"] == 0
        assert q["expenses"] == 0
        assert q["net"] == 0
        assert q["estimated_tax"] == 0

    assert data["annual_total_income"] == 0
    assert data["annual_total_expenses"] == 0
    assert data["annual_net"] == 0
    assert data["annual_estimated_tax"] == 0


@pytest.mark.asyncio
async def test_quarterly_report_with_data(
    client: AsyncClient, admin_user: User, seed_quarterly_data
):
    """Q1 income=5000, Q1 expense=2000 → net=3000, estimated_tax=750 at 25%."""
    resp = await client.get(
        "/api/reports/tax-quarterly",
        params={"year": 2026, "tax_rate": 25.0},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    q1 = data["quarters"][0]

    assert q1["quarter"] == 1
    assert q1["income"] == 5000.0
    assert q1["expenses"] == 2000.0
    assert q1["net"] == 3000.0
    assert q1["estimated_tax"] == 750.0


@pytest.mark.asyncio
async def test_quarterly_sums_equal_annual(
    client: AsyncClient, admin_user: User, seed_quarterly_data
):
    """Sum of per-quarter values must equal the annual totals."""
    resp = await client.get(
        "/api/reports/tax-quarterly",
        params={"year": 2026, "tax_rate": 25.0},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    q_income = sum(q["income"] for q in data["quarters"])
    q_expenses = sum(q["expenses"] for q in data["quarters"])
    q_estimated_tax = sum(q["estimated_tax"] for q in data["quarters"])

    assert q_income == pytest.approx(data["annual_total_income"])
    assert q_expenses == pytest.approx(data["annual_total_expenses"])
    assert q_estimated_tax == pytest.approx(data["annual_estimated_tax"])


@pytest.mark.asyncio
async def test_boundary_date_assignment(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    """Jan 1 → Q1, Apr 1 → Q2, Jul 1 → Q3, Oct 1 → Q4."""
    boundary_dates = [
        (date(2026, 1, 1), 1),
        (date(2026, 4, 1), 2),
        (date(2026, 7, 1), 3),
        (date(2026, 10, 1), 4),
    ]
    for d, _q in boundary_dates:
        db.add(
            Income(
                id=uuid.uuid4(),
                created_by=admin_user.id,
                category=IncomeCategory.OTHER,
                description=f"boundary {d.isoformat()}",
                amount=Decimal("1000.00"),
                currency="USD",
                date=d,
            )
        )
    await db.commit()

    resp = await client.get(
        "/api/reports/tax-quarterly",
        params={"year": 2026, "tax_rate": 25.0},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    quarters = resp.json()["data"]["quarters"]

    for _d, expected_q in boundary_dates:
        q = quarters[expected_q - 1]
        assert q["income"] >= 1000.0, f"Q{expected_q} should contain the boundary income"


@pytest.mark.asyncio
async def test_custom_tax_rate(
    client: AsyncClient, admin_user: User, seed_quarterly_data
):
    """Different tax_rate produces different estimated_tax."""
    resp_25 = await client.get(
        "/api/reports/tax-quarterly",
        params={"year": 2026, "tax_rate": 25.0},
        headers=auth_header(admin_user),
    )
    resp_10 = await client.get(
        "/api/reports/tax-quarterly",
        params={"year": 2026, "tax_rate": 10.0},
        headers=auth_header(admin_user),
    )
    assert resp_25.status_code == 200
    assert resp_10.status_code == 200

    tax_25 = resp_25.json()["data"]["annual_estimated_tax"]
    tax_10 = resp_10.json()["data"]["annual_estimated_tax"]

    assert tax_25 != tax_10
    # 10% tax should be less than 25% tax on the same positive income
    assert tax_10 < tax_25


@pytest.mark.asyncio
async def test_pdf_generation(
    client: AsyncClient, admin_user: User, seed_quarterly_data
):
    """GET quarterly PDF returns 200 with application/pdf content type."""
    resp = await client.get(
        "/api/reports/tax-quarterly/pdf",
        params={"year": 2026, "tax_rate": 25.0},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_year_over_year_with_no_previous(
    client: AsyncClient, admin_user: User, seed_quarterly_data
):
    """Only current-year data exists — previous year values should be 0."""
    resp = await client.get(
        "/api/reports/year-over-year",
        params={"year": 2026},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["current_year"] == 2026
    assert data["previous_year"] == 2025
    assert data["current_income"] > 0
    assert data["previous_income"] == 0
    assert data["previous_expenses"] == 0
    assert data["income_change_pct"] is None  # division by zero → None


@pytest.mark.asyncio
async def test_tax_deadlines(client: AsyncClient, admin_user: User):
    """4 deadlines returned for any year, each with a quarter label."""
    resp = await client.get(
        "/api/reports/tax-deadlines",
        params={"year": 2026},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    deadlines = resp.json()["data"]

    assert len(deadlines) == 4
    seen_quarters = {d["quarter"] for d in deadlines}
    assert seen_quarters == {1, 2, 3, 4}

    for d in deadlines:
        assert "quarter_label" in d
        assert "deadline_date" in d
        assert "description" in d


@pytest.mark.asyncio
async def test_unauthenticated_401(client: AsyncClient):
    """Requests without a token return 401."""
    endpoints = [
        ("/api/reports/tax-quarterly", {"year": 2026, "tax_rate": 25.0}),
        ("/api/reports/tax-quarterly/pdf", {"year": 2026, "tax_rate": 25.0}),
        ("/api/reports/year-over-year", {"year": 2026}),
        ("/api/reports/tax-deadlines", {"year": 2026}),
    ]
    for url, params in endpoints:
        resp = await client.get(url, params=params)
        assert resp.status_code == 401, f"{url} should require authentication"
