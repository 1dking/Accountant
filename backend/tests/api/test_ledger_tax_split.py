"""The ledger must carry income/expense NET of sales tax, with the tax itself
on 2100 Sales Tax Payable — otherwise the P&L (and the T2125 built on it)
overstates revenue by every dollar of GST/HST collected, and the T2125 and
GST34 disagree.

Pins the sprint-3 fix in accounting/ledger_reports.gather_postings.
"""
import uuid
from datetime import date
from decimal import Decimal

from app.accounting import ledger_reports
from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.cashbook.models import AccountType, CashbookEntry, EntryType, PaymentAccount

D = date(2026, 9, 6)


async def _user(db) -> User:
    u = User(
        id=uuid.uuid4(), email="taxsplit@ocidm.io", hashed_password=hash_password("TestPass123!"),
        full_name="Tax Split", role=Role.ADMIN, is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _account(db, u) -> PaymentAccount:
    a = PaymentAccount(
        user_id=u.id, name="BC Chequing", account_type=AccountType.BANK,
        currency="CAD", opening_balance=Decimal("0"), opening_balance_date=date(2026, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def _entry(db, u, acct, *, kind, total, tax=None, gst=None, pst=None):
    db.add(CashbookEntry(
        account_id=acct.id, entry_type=kind, date=D, description="x", user_id=u.id,
        total_amount=Decimal(total),
        tax_amount=Decimal(tax) if tax is not None else None,
        tax_gst_hst_amount=Decimal(gst) if gst is not None else None,
        tax_pst_amount=Decimal(pst) if pst is not None else None,
    ))
    await db.commit()


def _tb_row(tb: dict, code: str) -> dict | None:
    return next((r for r in tb["rows"] if r.get("code") == code), None)


async def test_income_posts_net_and_all_collected_tax_goes_to_payable(db):
    """BC sale $112 tax-inclusive: GST 5 + PST 7. Revenue is 100; 12 is a liability."""
    u = await _user(db)
    a = await _account(db, u)
    await _entry(db, u, a, kind=EntryType.INCOME, total="112.00", tax="12.00", gst="5.00", pst="7.00")

    postings = await ledger_reports.gather_postings(db, u)
    pl = ledger_reports.profit_loss(postings)
    tb = ledger_reports.trial_balance(postings)

    assert pl["total_income"] == Decimal("100.00")
    row = _tb_row(tb, "2100")
    assert row is not None, "Sales Tax Payable must appear once tax is recorded"
    assert Decimal(str(row["credit"])) - Decimal(str(row["debit"])) == Decimal("12.00")
    assert tb["balanced"] is True


async def test_expense_nets_only_the_gst_itc_and_keeps_pst_as_cost(db):
    """BC purchase $56: GST 2.50 (recoverable) + PST 3.50 (not). Expense is 53.50."""
    u = await _user(db)
    a = await _account(db, u)
    await _entry(db, u, a, kind=EntryType.EXPENSE, total="56.00", tax="6.00", gst="2.50", pst="3.50")

    postings = await ledger_reports.gather_postings(db, u)
    pl = ledger_reports.profit_loss(postings)
    tb = ledger_reports.trial_balance(postings)

    assert pl["total_expenses"] == Decimal("53.50")
    row = _tb_row(tb, "2100")
    assert Decimal(str(row["debit"])) - Decimal(str(row["credit"])) == Decimal("2.50")  # ITC reduces the liability
    assert tb["balanced"] is True


async def test_net_liability_is_collected_minus_itcs(db):
    u = await _user(db)
    a = await _account(db, u)
    await _entry(db, u, a, kind=EntryType.INCOME, total="112.00", tax="12.00", gst="5.00", pst="7.00")
    await _entry(db, u, a, kind=EntryType.EXPENSE, total="56.00", tax="6.00", gst="2.50", pst="3.50")

    postings = await ledger_reports.gather_postings(db, u)
    tb = ledger_reports.trial_balance(postings)
    row = _tb_row(tb, "2100")
    assert Decimal(str(row["credit"])) - Decimal(str(row["debit"])) == Decimal("9.50")
    pl = ledger_reports.profit_loss(postings)
    assert pl["net_profit"] == Decimal("100.00") - Decimal("53.50")


async def test_legacy_row_without_split_treats_tax_as_all_cra(db):
    """Pre-matrix entry: tax_amount set, tax_gst_hst_amount NULL → all of it is
    GST/HST (the old Ontario assumption). Expense nets the full tax."""
    u = await _user(db)
    a = await _account(db, u)
    await _entry(db, u, a, kind=EntryType.EXPENSE, total="113.00", tax="13.00")

    pl = ledger_reports.profit_loss(await ledger_reports.gather_postings(db, u))
    assert pl["total_expenses"] == Decimal("100.00")


async def test_no_tax_means_no_payable_line_and_unchanged_totals(db):
    u = await _user(db)
    a = await _account(db, u)
    await _entry(db, u, a, kind=EntryType.INCOME, total="500.00")

    postings = await ledger_reports.gather_postings(db, u)
    pl = ledger_reports.profit_loss(postings)
    tb = ledger_reports.trial_balance(postings)
    assert pl["total_income"] == Decimal("500.00")
    assert _tb_row(tb, "2100") is None
    assert tb["balanced"] is True


async def test_cash_side_still_moves_gross(db):
    """The customer paid the tax too — cash increases by the full 112."""
    u = await _user(db)
    a = await _account(db, u)
    await _entry(db, u, a, kind=EntryType.INCOME, total="112.00", tax="12.00", gst="5.00", pst="7.00")

    postings = await ledger_reports.gather_postings(db, u, date_to=D, include_opening=True)
    bs = ledger_reports.balance_sheet(postings)
    assert bs["total_assets"] == Decimal("112.00")
    assert bs["total_liabilities"] == Decimal("12.00")
    assert bs["balanced"] is True
