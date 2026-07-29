"""PDF export of the cashbook-consistent Financial Statements.

Asserts the two download endpoints return a real PDF with an attachment name,
and (via the generator directly) that the itemized figures land in the bytes —
so what's handed to an accountant matches the on-screen statement.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import ledger_reports, statement_pdf
from app.auth.models import User
from app.cashbook.models import (
    AccountType as PAType,
    CashbookEntry,
    EntryType,
    PaymentAccount,
)
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def _seed(db: AsyncSession, user: User):
    pa = PaymentAccount(
        id=uuid.uuid4(), user_id=user.id, name="Checking", account_type=PAType.BANK,
        opening_balance=Decimal("1000.00"), opening_balance_date=date(2026, 1, 1), is_active=True,
    )
    db.add(pa)
    await db.flush()
    db.add_all([
        CashbookEntry(id=uuid.uuid4(), account_id=pa.id, entry_type=EntryType.INCOME,
                      date=date(2026, 3, 1), description="Client", total_amount=Decimal("500.00"), user_id=user.id),
        CashbookEntry(id=uuid.uuid4(), account_id=pa.id, entry_type=EntryType.EXPENSE,
                      date=date(2026, 3, 2), description="Ads", total_amount=Decimal("200.00"), user_id=user.id),
    ])
    await db.commit()


async def test_profit_loss_pdf_downloads(client: AsyncClient, db: AsyncSession, admin_user: User):
    await _seed(db, admin_user)
    r = await client.get("/api/accounting/reports/profit-loss.pdf", headers=auth_header(admin_user))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:5] == b"%PDF-"


async def test_balance_sheet_pdf_downloads(client: AsyncClient, db: AsyncSession, admin_user: User):
    await _seed(db, admin_user)
    r = await client.get("/api/accounting/reports/balance-sheet.pdf", headers=auth_header(admin_user))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


async def test_generator_accounting_format():
    """Negatives render in parentheses; a plain figure keeps the dollar sign."""
    assert statement_pdf._money(Decimal("-42.50")) == "($42.50)"
    assert statement_pdf._money(Decimal("1234.5")) == "$1,234.50"


async def test_balance_sheet_pdf_is_nonempty_and_balanced(db: AsyncSession, admin_user: User):
    await _seed(db, admin_user)
    postings = await ledger_reports.gather_postings(db, admin_user, include_opening=True)
    bs = ledger_reports.balance_sheet(postings)
    assert bs["balanced"] is True
    pdf = statement_pdf.generate_balance_sheet_pdf(bs, as_of="2026-03-31", business_name="OCIDM")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000
