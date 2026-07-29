"""Cashbook-consistent P&L + a Balance Sheet that actually balances.

Both are derived from the same posting engine as the Trial Balance, so they tie
to the cashbook. The Balance Sheet folds in each account's opening balance and
closes net income into equity as Retained Earnings — the two bridges that make
Assets = Liabilities + Equity hold by construction.
"""
import uuid
from datetime import date
from decimal import Decimal

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.accounting import ledger_reports
from app.cashbook.models import (
    AccountType,
    CashbookEntry,
    EntryType,
    PaymentAccount,
)

D = date(2026, 3, 15)


async def _user(db) -> User:
    u = User(
        id=uuid.uuid4(), email="acct@ocidm.io", hashed_password=hash_password("TestPass123!"),
        full_name="Acct", role=Role.ADMIN, is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _account(db, u, *, opening="1000.00") -> PaymentAccount:
    a = PaymentAccount(
        user_id=u.id, name="CIBC Chequing", account_type=AccountType.BANK,
        currency="CAD", opening_balance=Decimal(opening), opening_balance_date=date(2026, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def _entry(db, u, acct, *, kind, amount) -> None:
    db.add(CashbookEntry(
        account_id=acct.id, entry_type=kind, date=D, description="x",
        total_amount=Decimal(amount), user_id=u.id,
    ))
    await db.commit()


async def test_profit_loss_nets_income_minus_expenses(db):
    u = await _user(db)
    a = await _account(db, u)
    await _entry(db, u, a, kind=EntryType.INCOME, amount="500.00")
    await _entry(db, u, a, kind=EntryType.EXPENSE, amount="200.00")

    postings = await ledger_reports.gather_postings(db, u)
    pl = ledger_reports.profit_loss(postings)
    assert pl["total_income"] == Decimal("500.00")
    assert pl["total_expenses"] == Decimal("200.00")
    assert pl["net_profit"] == Decimal("300.00")


async def test_balance_sheet_balances_with_opening_and_retained(db):
    u = await _user(db)
    a = await _account(db, u, opening="1000.00")
    await _entry(db, u, a, kind=EntryType.INCOME, amount="500.00")
    await _entry(db, u, a, kind=EntryType.EXPENSE, amount="200.00")

    postings = await ledger_reports.gather_postings(db, u, date_to=D, include_opening=True)
    bs = ledger_reports.balance_sheet(postings)

    # Cash = opening 1000 + income 500 - expense 200 = 1300.
    assert bs["total_assets"] == Decimal("1300.00")
    # Equity = Opening Balance Equity 1000 + Retained Earnings (net income 300) = 1300.
    assert bs["total_equity"] == Decimal("1300.00")
    assert bs["total_liabilities"] == Decimal("0.00")
    # The whole point: it balances.
    assert bs["balanced"] is True
    assert bs["total_assets"] == bs["total_liabilities_equity"]

    equity_names = {r["name"] for r in bs["equity"]}
    assert "Opening Balance Equity" in equity_names
    assert any("Retained Earnings" in n for n in equity_names)


async def test_profit_loss_itemizes_by_category(db):
    """Each cashbook category is its own P&L line — not collapsed into 'Other'."""
    from app.cashbook.models import CategoryType, TransactionCategory

    u = await _user(db)
    a = await _account(db, u)
    adv = TransactionCategory(name="Advertising", category_type=CategoryType.EXPENSE, display_order=7)
    meals = TransactionCategory(name="Meals", category_type=CategoryType.EXPENSE, display_order=12)
    db.add_all([adv, meals])
    await db.commit()
    await db.refresh(adv)
    await db.refresh(meals)
    db.add(CashbookEntry(account_id=a.id, entry_type=EntryType.EXPENSE, date=D,
                         description="x", total_amount=Decimal("30.00"), category_id=adv.id, user_id=u.id))
    db.add(CashbookEntry(account_id=a.id, entry_type=EntryType.EXPENSE, date=D,
                         description="y", total_amount=Decimal("20.00"), category_id=meals.id, user_id=u.id))
    await db.commit()

    pl = ledger_reports.profit_loss(await ledger_reports.gather_postings(db, u))
    names = {r["name"] for r in pl["expenses"]}
    assert "Advertising" in names
    assert "Meals" in names
    assert pl["total_expenses"] == Decimal("50.00")


async def test_opening_balance_off_by_default(db):
    """Trial Balance / P&L path must be unchanged — no opening postings unless asked."""
    u = await _user(db)
    a = await _account(db, u, opening="1000.00")
    await _entry(db, u, a, kind=EntryType.EXPENSE, amount="200.00")

    postings = await ledger_reports.gather_postings(db, u)  # include_opening defaults False
    assert not any(p.source == "opening" for p in postings)
