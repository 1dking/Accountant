"""GST/HST return summary from recorded cashbook tax (CRA GST34 lines).

Lines: 101 sales net of tax, 105 tax collected, 108 ITCs, 109 net. Reads the
cashbook's own tax_amount (not the legacy Invoice/Expense tables), and reports
nothing-recorded honestly rather than estimating.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import tax_return
from app.auth.models import User
from app.cashbook.models import (
    AccountType as PAType,
    CashbookEntry,
    EntryType,
    PaymentAccount,
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


async def _entry(db, user, pa, *, kind, amount, tax=None, when=date(2026, 3, 1)):
    db.add(CashbookEntry(
        id=uuid.uuid4(), account_id=pa.id, entry_type=kind, date=when, description="x",
        total_amount=Decimal(amount), tax_amount=(Decimal(tax) if tax is not None else None),
        user_id=user.id,
    ))


async def test_gst_return_lines(db: AsyncSession, admin_user: User):
    pa = await _pa(db, admin_user)
    # Revenue $1130 incl. $130 HST; expense $226 incl. $26 HST.
    await _entry(db, admin_user, pa, kind=EntryType.INCOME, amount="1130.00", tax="130.00")
    await _entry(db, admin_user, pa, kind=EntryType.EXPENSE, amount="226.00", tax="26.00")
    await db.commit()

    r = await tax_return.gst_hst_return(db, admin_user)
    assert r["line_101_sales"] == Decimal("1000.00")     # 1130 gross − 130 tax
    assert r["line_105_collected"] == Decimal("130.00")
    assert r["line_108_itc"] == Decimal("26.00")
    assert r["line_109_net_tax"] == Decimal("104.00")    # 130 − 26 owed to CRA
    assert r["owes_cra"] is True
    assert r["has_recorded_tax"] is True
    assert r["taxed_entry_count"] == 2


async def test_gst_return_empty_when_no_tax_recorded(db: AsyncSession, admin_user: User):
    pa = await _pa(db, admin_user)
    await _entry(db, admin_user, pa, kind=EntryType.INCOME, amount="500.00", tax=None)
    await db.commit()

    r = await tax_return.gst_hst_return(db, admin_user)
    assert r["line_105_collected"] == Decimal("0.00")
    assert r["line_108_itc"] == Decimal("0.00")
    assert r["line_109_net_tax"] == Decimal("0.00")
    assert r["has_recorded_tax"] is False
    assert r["taxed_entry_count"] == 0


async def test_gst_return_refund_when_itc_exceeds_collected(db: AsyncSession, admin_user: User):
    pa = await _pa(db, admin_user)
    await _entry(db, admin_user, pa, kind=EntryType.INCOME, amount="113.00", tax="13.00")
    await _entry(db, admin_user, pa, kind=EntryType.EXPENSE, amount="565.00", tax="65.00")
    await db.commit()

    r = await tax_return.gst_hst_return(db, admin_user)
    assert r["line_109_net_tax"] == Decimal("-52.00")    # 13 − 65 = refund
    assert r["owes_cra"] is False
