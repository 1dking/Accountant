"""Blended ROAS from the cashbook postings.

Ad spend is recognized from the resolved account name (advertising/marketing),
revenue from all income; ROAS = revenue / ad spend, trended by month and blended
overall. The figures must tie to the same postings the P&L reads.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import ledger_reports, marketing_reports
from app.auth.models import User
from app.cashbook.models import (
    AccountType as PAType,
    CashbookEntry,
    CategoryType,
    EntryType,
    PaymentAccount,
    TransactionCategory,
)

pytestmark = pytest.mark.asyncio


async def _pa(db, user):
    pa = PaymentAccount(
        id=uuid.uuid4(), user_id=user.id, name="Checking", account_type=PAType.BANK,
        opening_balance=Decimal("0"), opening_balance_date=date(2026, 1, 1), is_active=True,
    )
    db.add(pa)
    await db.flush()
    return pa


async def _cat(db, user, name, ctype):
    c = TransactionCategory(id=uuid.uuid4(), name=name, category_type=ctype, created_by=user.id)
    db.add(c)
    await db.flush()
    return c


async def _entry(db, user, pa, *, kind, amount, when, cat=None):
    db.add(CashbookEntry(
        id=uuid.uuid4(), account_id=pa.id, entry_type=kind, date=when,
        description="x", total_amount=Decimal(amount), user_id=user.id,
        category_id=cat.id if cat else None,
    ))


async def test_blended_roas_and_monthly_trend(db: AsyncSession, admin_user: User):
    pa = await _pa(db, admin_user)
    adv = await _cat(db, admin_user, "Advertising", CategoryType.EXPENSE)
    rent = await _cat(db, admin_user, "Rent", CategoryType.EXPENSE)
    # January: $1000 revenue, $250 ads, $500 rent (rent must NOT count as ad spend)
    await _entry(db, admin_user, pa, kind=EntryType.INCOME, amount="1000.00", when=date(2026, 1, 10))
    await _entry(db, admin_user, pa, kind=EntryType.EXPENSE, amount="250.00", when=date(2026, 1, 12), cat=adv)
    await _entry(db, admin_user, pa, kind=EntryType.EXPENSE, amount="500.00", when=date(2026, 1, 15), cat=rent)
    # February: $2000 revenue, $500 ads
    await _entry(db, admin_user, pa, kind=EntryType.INCOME, amount="2000.00", when=date(2026, 2, 5))
    await _entry(db, admin_user, pa, kind=EntryType.EXPENSE, amount="500.00", when=date(2026, 2, 8), cat=adv)
    await db.commit()

    postings = await ledger_reports.gather_postings(db, admin_user)
    mp = marketing_reports.marketing_performance(postings)

    assert mp["total_revenue"] == Decimal("3000.00")
    assert mp["total_ad_spend"] == Decimal("750.00")     # rent excluded
    assert mp["blended_roas"] == Decimal("4.00")         # 3000 / 750
    assert mp["net_after_ad_spend"] == Decimal("2250.00")

    by_month = {m["month"]: m for m in mp["months"]}
    assert by_month["2026-01"]["ad_spend"] == Decimal("250.00")
    assert by_month["2026-01"]["roas"] == Decimal("4.00")   # 1000 / 250
    assert by_month["2026-02"]["roas"] == Decimal("4.00")   # 2000 / 500

    ad_names = {r["name"] for r in mp["ad_spend_by_account"]}
    assert any("Advertising" in n for n in ad_names)


async def test_roas_none_when_no_ad_spend(db: AsyncSession, admin_user: User):
    pa = await _pa(db, admin_user)
    await _entry(db, admin_user, pa, kind=EntryType.INCOME, amount="900.00", when=date(2026, 3, 1))
    await db.commit()
    mp = marketing_reports.marketing_performance(await ledger_reports.gather_postings(db, admin_user))
    assert mp["total_ad_spend"] == Decimal("0")
    assert mp["blended_roas"] is None
