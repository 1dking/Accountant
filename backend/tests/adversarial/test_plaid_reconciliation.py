"""Bank reconciliation: book balance vs bank balance + un-booked count."""
import json
import uuid
from datetime import date
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.cashbook.models import AccountType, CashbookEntry, EntryType, PaymentAccount
from app.core.encryption import init_encryption_service
from app.integrations.plaid import service
from app.integrations.plaid.models import PlaidConnection, PlaidTransaction


@pytest.fixture(autouse=True)
def _enc():
    init_encryption_service(Fernet.generate_key().decode())


async def _user(db) -> User:
    u = User(
        id=uuid.uuid4(), email="op@ocidm.io", hashed_password=hash_password("TestPass123!"),
        full_name="Op", role=Role.ADMIN, is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def test_reconciliation_book_vs_bank_and_unbooked(db):
    u = await _user(db)  # personal — sees own only

    pa = PaymentAccount(
        user_id=u.id, name="CIBC", account_type=AccountType.BANK, currency="CAD",
        opening_balance=Decimal("0"), opening_balance_date=date(2026, 1, 1),
        plaid_account_id="acc-1",
    )
    db.add(pa)
    await db.commit()
    await db.refresh(pa)
    # Book balance = one $100 income entry.
    db.add(CashbookEntry(
        account_id=pa.id, entry_type=EntryType.INCOME, date=date(2026, 3, 1),
        description="x", total_amount=Decimal("100.00"), user_id=u.id,
    ))
    await db.commit()

    conn = PlaidConnection(
        user_id=u.id, institution_name="CIBC", institution_id="ins",
        encrypted_access_token="e", item_id=f"i-{uuid.uuid4().hex[:8]}",
        accounts_json=json.dumps([{
            "account_id": "acc-1", "name": "Chequing", "mask": "1234",
            "iso_currency_code": "CAD", "current_balance": 100.0,
        }]),
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    txn = PlaidTransaction(
        plaid_connection_id=conn.id, plaid_transaction_id=f"t-{uuid.uuid4().hex[:8]}",
        account_id="acc-1", amount=Decimal("5"), date=date(2026, 3, 2),
        name="x", is_income=False, is_categorized=False,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    rows = await service.reconciliation_summary(db, u)
    assert len(rows) == 1
    r = rows[0]
    assert Decimal(r["book_balance"]) == Decimal("100")
    assert Decimal(r["bank_balance"]) == Decimal("100")
    assert Decimal(r["difference"]) == Decimal("0")
    assert r["unbooked_count"] == 1
    assert r["reconciled"] is False  # something still un-booked

    # Book the last transaction -> nothing un-booked, balances match -> reconciled.
    txn.is_categorized = True
    await db.commit()
    r2 = (await service.reconciliation_summary(db, u))[0]
    assert r2["unbooked_count"] == 0
    assert r2["reconciled"] is True
