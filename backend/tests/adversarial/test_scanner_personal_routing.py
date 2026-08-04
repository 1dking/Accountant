"""Scanner Personal/Business router — tagging a shared-feed transaction Personal.

A "personal" tag on a business bank account must (1) post an Owner's Draw/
Contribution EQUITY entry on the business account — so it stays in the account
balance / reconciliation but drops out of the P&L + tax — AND (2) copy the item
into the Personal ledger. Business tagging is unchanged. Idempotent both ways.
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app.accounting import ledger_reports
from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.cashbook.models import CashbookEntry, CategoryType, EntryType, TransactionCategory
from app.cashbook.service import get_account_current_balance
from app.core.encryption import init_encryption_service
from app.integrations.plaid import service as plaid_service
from app.integrations.plaid.models import PlaidConnection, PlaidTransaction
from app.integrations.plaid.schemas import CategorizeTransactionRequest
from app.personal.models import PersonalTransaction

D = date(2026, 3, 15)
PLAID_ACCOUNT_ID = "acc-1"


@pytest.fixture(autouse=True)
def _encryption():
    init_encryption_service(Fernet.generate_key().decode())


async def _seed_equity(db):
    for name in ("Owner's Draw", "Owner's Contribution"):
        db.add(TransactionCategory(id=uuid.uuid4(), name=name, category_type=CategoryType.EQUITY, is_system=True))
    await db.commit()


async def _user(db):
    u = User(id=uuid.uuid4(), email="op@ocidm.io", hashed_password=hash_password("TestPass123!"),
             full_name="Op", role=Role.ADMIN, is_active=True)
    db.add(u); await db.commit(); await db.refresh(u); return u


async def _conn(db, user):
    accounts = [{"account_id": PLAID_ACCOUNT_ID, "name": "Chequing", "type": "depository",
                 "subtype": "checking", "mask": "1234", "iso_currency_code": "CAD"}]
    conn = PlaidConnection(user_id=user.id, institution_name="CIBC", institution_id="ins_cibc",
                           encrypted_access_token="enc", item_id=f"item-{uuid.uuid4().hex[:12]}",
                           accounts_json=json.dumps(accounts))
    db.add(conn); await db.commit(); await db.refresh(conn); return conn


async def _txn(db, conn, *, amount="50.00", is_income=False):
    t = PlaidTransaction(plaid_connection_id=conn.id, plaid_transaction_id=f"txn-{uuid.uuid4().hex[:12]}",
                         account_id=PLAID_ACCOUNT_ID, amount=Decimal(amount), date=D,
                         name="Acme Coffee", merchant_name="Acme Coffee", is_income=is_income, is_categorized=False)
    db.add(t); await db.commit(); await db.refresh(t); return t


def _req(**over):
    base = dict(as_type="cashbook")
    base.update(over)
    return CategorizeTransactionRequest(**base)


async def test_personal_tag_creates_equity_entry_and_personal_copy(db):
    await _seed_equity(db)
    user = await _user(db)
    conn = await _conn(db, user)
    txn = await _txn(db, conn, amount="50.00", is_income=False)  # money out

    result = await plaid_service.categorize_transaction(
        db, txn.id, _req(scope="personal"), user, SimpleNamespace(),
    )

    # Business side: an Owner's Draw (equity) CashbookEntry.
    assert result.matched_cashbook_entry_id is not None
    entry = (await db.execute(select(CashbookEntry).where(CashbookEntry.id == result.matched_cashbook_entry_id))).scalar_one()
    cat = (await db.execute(select(TransactionCategory).where(TransactionCategory.id == entry.category_id))).scalar_one()
    assert cat.name == "Owner's Draw"
    assert cat.category_type == CategoryType.EQUITY

    # Excluded from the P&L …
    pl = ledger_reports.profit_loss(await ledger_reports.gather_postings(db, user))
    assert pl["total_expenses"] == Decimal("0.00")
    # … but still in the account balance / reconciliation (money left the account).
    assert await get_account_current_balance(db, entry.account_id) == Decimal("-50.00")

    # Personal side: a copy in the Personal ledger.
    assert result.matched_personal_transaction_id is not None
    ptxn = (await db.execute(select(PersonalTransaction).where(PersonalTransaction.user_id == user.id))).scalar_one()
    assert ptxn.direction == "out"
    assert ptxn.amount == Decimal("50.00")
    assert ptxn.source == "plaid" and ptxn.source_id == txn.plaid_transaction_id


async def test_personal_contribution_uses_contribution_category_and_in_direction(db):
    await _seed_equity(db)
    user = await _user(db)
    conn = await _conn(db, user)
    txn = await _txn(db, conn, amount="200.00", is_income=True)  # money in

    result = await plaid_service.categorize_transaction(db, txn.id, _req(scope="personal"), user, SimpleNamespace())
    entry = (await db.execute(select(CashbookEntry).where(CashbookEntry.id == result.matched_cashbook_entry_id))).scalar_one()
    cat = (await db.execute(select(TransactionCategory).where(TransactionCategory.id == entry.category_id))).scalar_one()
    assert cat.name == "Owner's Contribution"
    ptxn = (await db.execute(select(PersonalTransaction).where(PersonalTransaction.user_id == user.id))).scalar_one()
    assert ptxn.direction == "in"


async def test_personal_tag_is_idempotent(db):
    await _seed_equity(db)
    user = await _user(db)
    conn = await _conn(db, user)
    txn = await _txn(db, conn, amount="50.00")

    await plaid_service.categorize_transaction(db, txn.id, _req(scope="personal"), user, SimpleNamespace())
    await plaid_service.categorize_transaction(db, txn.id, _req(scope="personal"), user, SimpleNamespace())

    n_cb = await db.scalar(select(func.count(CashbookEntry.id)).where(CashbookEntry.user_id == user.id))
    n_p = await db.scalar(select(func.count(PersonalTransaction.id)).where(PersonalTransaction.user_id == user.id))
    assert n_cb == 1
    assert n_p == 1


async def test_business_tag_unchanged_no_personal_copy(db):
    await _seed_equity(db)
    user = await _user(db)
    conn = await _conn(db, user)
    txn = await _txn(db, conn, amount="50.00")

    result = await plaid_service.categorize_transaction(db, txn.id, _req(scope="business"), user, SimpleNamespace())
    assert result.matched_personal_transaction_id is None
    n_p = await db.scalar(select(func.count(PersonalTransaction.id)).where(PersonalTransaction.user_id == user.id))
    assert n_p == 0
    # A regular business expense hits the P&L normally.
    pl = ledger_reports.profit_loss(await ledger_reports.gather_postings(db, user))
    assert pl["total_expenses"] == Decimal("50.00")
