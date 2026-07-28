"""Bank Scanner: posting a synced Plaid transaction to the Cashbook.

The Cashbook is the PRIMARY destination for a reviewed bank transaction. These
tests pin the behaviour that makes that safe and turnkey:

  * The CIBC bank account is auto-provisioned once and reused (no manual setup).
  * A post lands as a CashbookEntry(source="plaid") linked back to the txn.
  * The same bank transaction can never post twice (idempotency).
  * A hand-entered Cashbook row of the same amount/date is flagged, not silently
    doubled — unless the user confirms.
  * Amounts carry the account's real currency (CAD), not a hardcoded USD.
  * Backfilling into a CLOSED accounting period is refused (tax integrity).
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.cashbook.models import AccountType, CashbookEntry, EntryType, PaymentAccount
from app.core.encryption import init_encryption_service
from app.core.exceptions import ValidationError
from app.integrations.plaid import service as plaid_service
from app.integrations.plaid.models import PlaidConnection, PlaidTransaction
from app.integrations.plaid.reconcile import (
    PossibleDuplicateError,
    find_duplicate_records,
)
from app.integrations.plaid.schemas import CategorizeTransactionRequest

D = date(2026, 3, 15)
PLAID_ACCOUNT_ID = "acc-1"


@pytest.fixture(autouse=True)
def _encryption():
    # PlaidTransaction.amount/name/... are encrypted columns.
    init_encryption_service(Fernet.generate_key().decode())


async def make_user(db, *, email="op@ocidm.io") -> User:
    u = User(
        id=uuid.uuid4(), email=email, hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0], role=Role.ADMIN, is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def make_connection(db, user, *, institution="CIBC") -> PlaidConnection:
    accounts = [{
        "account_id": PLAID_ACCOUNT_ID, "name": "Chequing", "type": "depository",
        "subtype": "checking", "mask": "1234", "iso_currency_code": "CAD",
    }]
    conn = PlaidConnection(
        user_id=user.id, institution_name=institution, institution_id="ins_cibc",
        encrypted_access_token="enc", item_id=f"item-{uuid.uuid4().hex[:12]}",
        accounts_json=json.dumps(accounts),
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def make_txn(db, conn, *, amount="50.00", txn_date=D, is_income=False) -> PlaidTransaction:
    txn = PlaidTransaction(
        plaid_connection_id=conn.id, plaid_transaction_id=f"txn-{uuid.uuid4().hex[:12]}",
        account_id=PLAID_ACCOUNT_ID, amount=Decimal(amount), date=txn_date,
        name="Acme Coffee", merchant_name="Acme Coffee", is_income=is_income,
        is_categorized=False,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


async def make_manual_account(db, user, *, currency="CAD") -> PaymentAccount:
    acct = PaymentAccount(
        user_id=user.id, name="Manual Cash", account_type=AccountType.CASH,
        currency=currency, opening_balance=0, opening_balance_date=D,
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return acct


async def make_cashbook_entry(db, user, account, *, amount="50.00", entry_date=D,
                              source="manual", entry_type=EntryType.EXPENSE) -> CashbookEntry:
    entry = CashbookEntry(
        account_id=account.id, entry_type=entry_type, date=entry_date,
        description="Hand-entered coffee", total_amount=Decimal(amount),
        user_id=user.id, source=source, source_id=None,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def count_cashbook_entries(db, user) -> int:
    return int(await db.scalar(
        select(func.count(CashbookEntry.id)).where(CashbookEntry.user_id == user.id)
    ) or 0)


async def cashbook_req(**over):
    base = dict(as_type="cashbook")
    base.update(over)
    return CategorizeTransactionRequest(**base)


# ---------------------------------------------------------------------------
# Account provisioning
# ---------------------------------------------------------------------------


async def test_get_or_create_bank_account_is_idempotent(db):
    user = await make_user(db)
    conn = await make_connection(db, user)

    first = await plaid_service.get_or_create_bank_account(db, user, conn, PLAID_ACCOUNT_ID)
    await db.commit()
    second = await plaid_service.get_or_create_bank_account(db, user, conn, PLAID_ACCOUNT_ID)

    assert first.id == second.id
    assert first.account_type == AccountType.BANK
    assert first.plaid_account_id == PLAID_ACCOUNT_ID
    assert first.currency == "CAD"
    assert first.name == "CIBC Chequing …1234"
    # Exactly one account exists — the second call did not create a duplicate.
    n = await db.scalar(select(func.count(PaymentAccount.id)).where(PaymentAccount.user_id == user.id))
    assert n == 1


# ---------------------------------------------------------------------------
# Posting to the Cashbook
# ---------------------------------------------------------------------------


async def test_cashbook_post_creates_linked_entry_and_account(db):
    user = await make_user(db)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="50.00")

    result = await plaid_service.categorize_transaction(
        db, txn.id, await cashbook_req(), user, SimpleNamespace(),
    )

    assert result.is_categorized is True
    assert result.matched_cashbook_entry_id is not None

    entry = (await db.execute(
        select(CashbookEntry).where(CashbookEntry.id == result.matched_cashbook_entry_id)
    )).scalar_one()
    assert entry.source == "plaid"
    assert entry.source_id == txn.plaid_transaction_id
    assert entry.entry_type == EntryType.EXPENSE       # is_income False -> expense
    assert entry.total_amount == Decimal("50.00")
    assert entry.date == D

    # Bank account was auto-provisioned (no manual setup) and is a BANK account.
    acct = (await db.execute(
        select(PaymentAccount).where(PaymentAccount.id == entry.account_id)
    )).scalar_one()
    assert acct.account_type == AccountType.BANK
    assert acct.plaid_account_id == PLAID_ACCOUNT_ID
    assert acct.currency == "CAD"


async def test_cashbook_entry_type_override(db):
    user = await make_user(db)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="80.00", is_income=False)  # bank says expense

    result = await plaid_service.categorize_transaction(
        db, txn.id, await cashbook_req(entry_type="income"), user, SimpleNamespace(),
    )
    entry = (await db.execute(
        select(CashbookEntry).where(CashbookEntry.id == result.matched_cashbook_entry_id)
    )).scalar_one()
    assert entry.entry_type == EntryType.INCOME  # override wins


async def test_cashbook_post_is_idempotent(db):
    user = await make_user(db)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="50.00")

    first = await plaid_service.categorize_transaction(
        db, txn.id, await cashbook_req(), user, SimpleNamespace(),
    )
    second = await plaid_service.categorize_transaction(
        db, txn.id, await cashbook_req(), user, SimpleNamespace(),
    )

    assert first.matched_cashbook_entry_id == second.matched_cashbook_entry_id
    assert await count_cashbook_entries(db, user) == 1  # not two


# ---------------------------------------------------------------------------
# Deduplication against hand-entered Cashbook rows
# ---------------------------------------------------------------------------


async def test_cashbook_post_flags_manual_duplicate(db):
    user = await make_user(db)
    manual_acct = await make_manual_account(db, user)
    await make_cashbook_entry(db, user, manual_acct, amount="50.00", entry_date=D)  # by hand
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="50.00", txn_date=D)

    before = await count_cashbook_entries(db, user)
    with pytest.raises(PossibleDuplicateError) as ei:
        await plaid_service.categorize_transaction(
            db, txn.id, await cashbook_req(confirm_duplicate=False), user, SimpleNamespace(),
        )
    assert ei.value.status_code == 409
    assert ei.value.details["possible_duplicates"]
    assert await count_cashbook_entries(db, user) == before  # nothing posted


async def test_cashbook_post_with_confirm_posts_anyway(db):
    user = await make_user(db)
    manual_acct = await make_manual_account(db, user)
    await make_cashbook_entry(db, user, manual_acct, amount="50.00", entry_date=D)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="50.00", txn_date=D)

    before = await count_cashbook_entries(db, user)
    result = await plaid_service.categorize_transaction(
        db, txn.id, await cashbook_req(confirm_duplicate=True), user, SimpleNamespace(),
    )
    assert result.is_categorized is True
    assert await count_cashbook_entries(db, user) == before + 1


async def test_find_duplicate_records_cashbook_excludes_our_plaid_posts(db):
    user = await make_user(db)
    acct = await make_manual_account(db, user)
    await make_cashbook_entry(db, user, acct, amount="50.00", source="manual")
    await make_cashbook_entry(db, user, acct, amount="50.00", source="plaid")

    dups = await find_duplicate_records(
        db, user, amount=Decimal("50.00"), txn_date=D, kind="cashbook",
    )
    # Only the hand-entered row is a candidate — a prior Plaid post of the same
    # amount is a real separate charge, not a double.
    assert len(dups) == 1
    assert all(d["kind"] == "cashbook" for d in dups)


# ---------------------------------------------------------------------------
# Currency + closed period
# ---------------------------------------------------------------------------


async def test_expense_post_uses_account_currency_not_usd(db):
    """The old bug hardcoded USD; a CIBC (CAD) account must post CAD."""
    from app.accounting.models import Expense

    user = await make_user(db)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="42.00")

    await plaid_service.categorize_transaction(
        db, txn.id, CategorizeTransactionRequest(as_type="expense"), user, SimpleNamespace(),
    )
    exp = (await db.execute(select(Expense).where(Expense.user_id == user.id))).scalar_one()
    assert exp.currency == "CAD"


async def test_cashbook_post_into_closed_period_is_refused(db):
    from app.accounting.period_service import close_period

    user = await make_user(db)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="50.00", txn_date=D)

    await close_period(db, D.year, D.month, user)  # lock March 2026

    with pytest.raises(ValidationError):
        await plaid_service.categorize_transaction(
            db, txn.id, await cashbook_req(), user, SimpleNamespace(),
        )
    # Nothing posted while the period is closed.
    assert await count_cashbook_entries(db, user) == 0
