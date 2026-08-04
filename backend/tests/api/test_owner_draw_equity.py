"""Owner's Draw / Contribution — commingled personal money in a BUSINESS account.

Tagged EQUITY, so it is EXCLUDED from the business P&L and GST/HST but STILL
counts in the account balance / bank reconciliation. This is the in-place fix for
transactions already sitting in the business books (distinct from Personal mode's
separate ledger).
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import ledger_reports, tax_return
from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.cashbook.models import (
    AccountType as PAType,
    CashbookEntry,
    CategoryType,
    EntryType,
    PaymentAccount,
    TransactionCategory,
)
from app.cashbook.service import get_account_current_balance

pytestmark = pytest.mark.asyncio

D = date(2026, 3, 15)


async def _user(db):
    u = User(id=uuid.uuid4(), email="oe@test.com", hashed_password=hash_password("TestPass123!"),
             full_name="OE", role=Role.ADMIN, is_active=True)
    db.add(u); await db.commit(); await db.refresh(u); return u


async def _account(db, u, opening="1000.00"):
    a = PaymentAccount(id=uuid.uuid4(), user_id=u.id, name="CIBC", account_type=PAType.BANK,
                       opening_balance=Decimal(opening), opening_balance_date=date(2026, 1, 1), is_active=True)
    db.add(a); await db.commit(); await db.refresh(a); return a


async def _cat(db, name, ctype):
    c = TransactionCategory(id=uuid.uuid4(), name=name, category_type=ctype)
    db.add(c); await db.commit(); await db.refresh(c); return c


async def _entry(db, u, a, kind, amount, cat=None, tax=None):
    db.add(CashbookEntry(id=uuid.uuid4(), account_id=a.id, entry_type=kind, date=D, description="x",
                         total_amount=Decimal(amount), category_id=(cat.id if cat else None),
                         tax_amount=(Decimal(tax) if tax else None), user_id=u.id))
    await db.commit()


async def test_owners_draw_excluded_from_pl_but_in_balance(db: AsyncSession):
    u = await _user(db); a = await _account(db, u, "1000.00")
    adv = await _cat(db, "Advertising", CategoryType.EXPENSE)
    draw = await _cat(db, "Owner's Draw", CategoryType.EQUITY)
    await _entry(db, u, a, EntryType.EXPENSE, "200.00", cat=adv)    # business expense
    await _entry(db, u, a, EntryType.EXPENSE, "300.00", cat=draw)   # personal draw (money out)

    pl = ledger_reports.profit_loss(await ledger_reports.gather_postings(db, u))
    assert pl["total_expenses"] == Decimal("200.00")               # draw NOT in expenses
    assert "Owner's Draw" not in {r["name"] for r in pl["expenses"]}
    assert "Advertising" in {r["name"] for r in pl["expenses"]}

    # …but the draw still moved the bank balance: 1000 − 200 − 300 = 500.
    assert await get_account_current_balance(db, a.id) == Decimal("500.00")


async def test_owners_contribution_excluded_from_income(db: AsyncSession):
    u = await _user(db); a = await _account(db, u, "0.00")
    fees = await _cat(db, "Fees", CategoryType.INCOME)
    contrib = await _cat(db, "Owner's Contribution", CategoryType.EQUITY)
    await _entry(db, u, a, EntryType.INCOME, "500.00", cat=fees)
    await _entry(db, u, a, EntryType.INCOME, "1000.00", cat=contrib)  # personal money in

    pl = ledger_reports.profit_loss(await ledger_reports.gather_postings(db, u))
    assert pl["total_income"] == Decimal("500.00")                  # contribution NOT in income
    assert await get_account_current_balance(db, a.id) == Decimal("1500.00")  # both in balance


async def test_balance_sheet_includes_equity_and_balances(db: AsyncSession):
    u = await _user(db); a = await _account(db, u, "1000.00")
    draw = await _cat(db, "Owner's Draw", CategoryType.EQUITY)
    await _entry(db, u, a, EntryType.EXPENSE, "300.00", cat=draw)

    bs = ledger_reports.balance_sheet(await ledger_reports.gather_postings(db, u, include_opening=True))
    assert bs["balanced"] is True
    assert bs["total_assets"] == Decimal("700.00")                 # 1000 opening − 300 draw
    assert any("Owner's Draw" in r["name"] for r in bs["equity"])


async def test_gst_return_excludes_equity(db: AsyncSession):
    u = await _user(db); a = await _account(db, u)
    adv = await _cat(db, "Advertising", CategoryType.EXPENSE)
    draw = await _cat(db, "Owner's Draw", CategoryType.EQUITY)
    await _entry(db, u, a, EntryType.EXPENSE, "113.00", cat=adv, tax="13.00")   # business ITC
    await _entry(db, u, a, EntryType.EXPENSE, "226.00", cat=draw, tax="26.00")  # personal — must NOT be an ITC

    r = await tax_return.gst_hst_return(db, u)
    assert r["line_108_itc"] == Decimal("13.00")                   # only the business $13


async def test_normal_categories_unchanged(db: AsyncSession):
    """A regular business expense still hits the P&L exactly as before."""
    u = await _user(db); a = await _account(db, u)
    adv = await _cat(db, "Advertising", CategoryType.EXPENSE)
    await _entry(db, u, a, EntryType.EXPENSE, "150.00", cat=adv)
    pl = ledger_reports.profit_loss(await ledger_reports.gather_postings(db, u))
    assert pl["total_expenses"] == Decimal("150.00")
