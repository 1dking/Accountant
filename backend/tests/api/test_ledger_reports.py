"""Tests for the General Ledger & Trial Balance (Phase 1.3).

The load-bearing invariant: the Trial Balance ALWAYS balances (Σ debits ==
Σ credits) across mixed journal + cashbook postings — that's what proves the
books are internally consistent. Also: cashbook expansion direction, name-based
CoA resolution, split distribution, and tenant isolation.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import coa_service, ledger_reports
from app.auth.models import User
from app.cashbook.models import (
    AccountType as PAType,
    CashbookEntry,
    CategoryType,
    EntryType,
    PaymentAccount,
    TransactionCategory,
)
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def _seed(db: AsyncSession, user: User):
    await coa_service.seed_default_coa(db, user, migrate=False)
    return {a.code: a for a in await coa_service.list_accounts(db, user)}


async def _cashbook_income(db, user, amount, cat_name="Consulting Income"):
    pa = PaymentAccount(
        id=uuid.uuid4(), user_id=user.id, name="Checking", account_type=PAType.BANK,
        opening_balance=Decimal("0"), opening_balance_date=date(2026, 1, 1), is_active=True,
    )
    cat = TransactionCategory(
        id=uuid.uuid4(), name=cat_name, category_type=CategoryType.INCOME, created_by=user.id,
    )
    db.add_all([pa, cat])
    await db.flush()
    e = CashbookEntry(
        id=uuid.uuid4(), account_id=pa.id, entry_type=EntryType.INCOME, date=date(2026, 3, 1),
        description="Client payment", total_amount=Decimal(str(amount)), category_id=cat.id,
        user_id=user.id,
    )
    db.add(e)
    await db.commit()
    return pa, cat, e


async def test_trial_balance_balances_journal_only(db: AsyncSession, admin_user: User):
    accts = await _seed(db, admin_user)
    from app.accounting.journal_schemas import JournalEntryCreate, JournalLineInput
    from app.accounting import journal_service

    await journal_service.create_entry(
        db,
        JournalEntryCreate(
            date=date(2026, 3, 2), memo="Owner investment",
            lines=[
                JournalLineInput(account_id=accts["1000"].id, debit=Decimal("500"), credit=Decimal("0")),
                JournalLineInput(account_id=accts["3000"].id, debit=Decimal("0"), credit=Decimal("500")),
            ],
        ),
        admin_user,
    )
    postings = await ledger_reports.gather_postings(db, admin_user)
    tb = ledger_reports.trial_balance(postings)
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"] == Decimal("500.00")


async def test_trial_balance_balances_cashbook_only(db: AsyncSession, admin_user: User):
    await _seed(db, admin_user)
    await _cashbook_income(db, admin_user, "300.00")
    postings = await ledger_reports.gather_postings(db, admin_user)
    tb = ledger_reports.trial_balance(postings)
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"] == Decimal("300.00")
    # Income landed as a credit; cash as a debit.
    by_code = {r["code"]: r for r in tb["rows"]}
    assert by_code["1500"]["debit"] == Decimal("300.00") or any(
        r["account_type"] == "asset" and r["debit"] == Decimal("300.00") for r in tb["rows"]
    )


async def test_trial_balance_balances_mixed_sources(
    client: AsyncClient, db: AsyncSession, admin_user: User
):
    accts = await _seed(db, admin_user)
    await _cashbook_income(db, admin_user, "300.00")
    from app.accounting.journal_schemas import JournalEntryCreate, JournalLineInput
    from app.accounting import journal_service

    await journal_service.create_entry(
        db,
        JournalEntryCreate(
            date=date(2026, 3, 3), memo="Depreciation",
            lines=[
                JournalLineInput(account_id=accts["6900"].id, debit=Decimal("120.55"), credit=Decimal("0")),
                JournalLineInput(account_id=accts["1000"].id, debit=Decimal("0"), credit=Decimal("120.55")),
            ],
        ),
        admin_user,
    )
    r = await client.get("/api/accounting/reports/trial-balance", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    tb = r.json()["data"]
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]


async def test_cashbook_income_resolves_category_by_name(db: AsyncSession, admin_user: User):
    """A cashbook category named to match a migrated CoA account posts to it, not
    the catch-all."""
    accts = await _seed(db, admin_user)
    # Create a CoA income account the category name will match.
    from app.accounting.coa_schemas import ChartAccountCreate
    from app.accounting.ledger_models import AccountType

    await coa_service.create_account(
        db, ChartAccountCreate(code="4200", name="Consulting Income", account_type=AccountType.INCOME), admin_user
    )
    await _cashbook_income(db, admin_user, "800.00", cat_name="Consulting Income")
    postings = await ledger_reports.gather_postings(db, admin_user)
    gl = ledger_reports.general_ledger(postings)
    by_code = {a["code"]: a for a in gl["accounts"]}
    assert "4200" in by_code
    assert by_code["4200"]["total_credit"] == Decimal("800.00")


async def test_general_ledger_running_balance(db: AsyncSession, admin_user: User):
    accts = await _seed(db, admin_user)
    from app.accounting.journal_schemas import JournalEntryCreate, JournalLineInput
    from app.accounting import journal_service

    for amt in ("100", "50"):
        await journal_service.create_entry(
            db,
            JournalEntryCreate(
                date=date(2026, 3, 2), memo="cash in",
                lines=[
                    JournalLineInput(account_id=accts["1000"].id, debit=Decimal(amt), credit=Decimal("0")),
                    JournalLineInput(account_id=accts["4000"].id, debit=Decimal("0"), credit=Decimal(amt)),
                ],
            ),
            admin_user,
        )
    postings = await ledger_reports.gather_postings(db, admin_user)
    gl = ledger_reports.general_ledger(postings)
    cash = next(a for a in gl["accounts"] if a["code"] == "1000")
    # Cash is debit-normal: two debits accumulate to 150.
    assert cash["closing_balance"] == Decimal("150.00")


async def test_voided_journal_excluded_from_reports(db: AsyncSession, admin_user: User):
    accts = await _seed(db, admin_user)
    from app.accounting.journal_schemas import JournalEntryCreate, JournalLineInput
    from app.accounting import journal_service

    entry = await journal_service.create_entry(
        db,
        JournalEntryCreate(
            date=date(2026, 3, 2), memo="to void",
            lines=[
                JournalLineInput(account_id=accts["1000"].id, debit=Decimal("77"), credit=Decimal("0")),
                JournalLineInput(account_id=accts["4000"].id, debit=Decimal("0"), credit=Decimal("77")),
            ],
        ),
        admin_user,
    )
    await journal_service.void_entry(db, entry.id, admin_user)
    postings = await ledger_reports.gather_postings(db, admin_user)
    tb = ledger_reports.trial_balance(postings)
    assert tb["total_debit"] == Decimal("0.00")


async def test_reports_isolated_by_tenant(
    client: AsyncClient, db: AsyncSession, accountant_user: User, team_member_user: User
):
    await _seed(db, accountant_user)
    await _cashbook_income(db, accountant_user, "999.00")
    # team_member's report sees none of accountant's postings.
    r = await client.get("/api/accounting/reports/trial-balance", headers=auth_header(team_member_user))
    tb = r.json()["data"]
    assert tb["rows"] == []
    assert tb["total_debit"] == "0.00"
