"""Plaid production go-live safety: operator-only access gate + dedup guard.

Proves the two things that matter before connecting real banks:
  1. Link is limited to the allow-listed operator emails (self-serve tenant
     admins, who are ADMINs of their own tenant, are refused).
  2. Categorizing a Plaid transaction cannot silently double-count something the
     user already entered by hand — it is flagged for confirmation (manual) or
     skipped (automatic rules).
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import func, select

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.core.encryption import init_encryption_service
from app.integrations.plaid.categorization_models import (
    CategorizationRule,
    MatchField,
    MatchType,
)
from app.integrations.plaid.categorization_service import apply_rules_to_transaction
from app.integrations.plaid.models import PlaidConnection, PlaidTransaction
from app.integrations.plaid.reconcile import (
    PossibleDuplicateError,
    find_duplicate_records,
)
from app.integrations.plaid.router import require_plaid_link_access
from app.integrations.plaid.schemas import CategorizeTransactionRequest
from app.integrations.plaid import service as plaid_service

D = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _encryption():
    # Encrypted columns (PlaidTransaction.amount/name/...) need an initialised
    # service; pin a real key per test so writes+reads round-trip.
    init_encryption_service(Fernet.generate_key().decode())


async def make_user(db, *, email, role=Role.ADMIN, mfa_enabled=False) -> User:
    u = User(
        id=uuid.uuid4(), email=email, hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0], role=role, is_active=True, mfa_enabled=mfa_enabled,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def make_connection(db, user) -> PlaidConnection:
    conn = PlaidConnection(
        user_id=user.id, institution_name="Test Bank", institution_id="ins_1",
        encrypted_access_token="enc", item_id=f"item-{uuid.uuid4().hex[:12]}",
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def make_txn(db, conn, *, amount="50.00", txn_date=D, is_income=False) -> PlaidTransaction:
    txn = PlaidTransaction(
        plaid_connection_id=conn.id, plaid_transaction_id=f"txn-{uuid.uuid4().hex[:12]}",
        account_id="acc-1", amount=Decimal(amount), date=txn_date,
        name="Acme Coffee", merchant_name="Acme Coffee", is_income=is_income,
        is_categorized=False,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


async def make_expense(db, user, *, amount="50.00", exp_date=D):
    from app.accounting.models import Expense

    e = Expense(user_id=user.id, amount=Decimal(amount), date=exp_date,
                vendor_name="Acme Coffee", description="Acme Coffee")
    db.add(e)
    await db.commit()
    return e


async def make_income(db, user, *, amount="50.00", inc_date=D):
    from app.income.models import Income

    i = Income(created_by=user.id, amount=Decimal(amount), date=inc_date,
               description="Client payment", payment_method="bank_transfer")
    db.add(i)
    await db.commit()
    return i


async def count_expenses(db, user) -> int:
    from app.accounting.models import Expense

    return int(await db.scalar(select(func.count(Expense.id)).where(Expense.user_id == user.id)) or 0)


def link_request(**settings_over):
    base = dict(plaid_link_enabled=True, plaid_link_allowed_emails="")
    base.update(settings_over)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(**base))))


# ---------------------------------------------------------------------------
# Access gate — operator allow-list
# ---------------------------------------------------------------------------

ALLOW = "nathano@ocidm.io,shivonneo@ocidm.io"


async def test_allowlisted_operator_passes(db):
    op = await make_user(db, email="nathano@ocidm.io", role=Role.ADMIN, mfa_enabled=True)
    req = link_request(plaid_link_enabled=True, plaid_link_allowed_emails=ALLOW)
    assert await require_plaid_link_access(req, op, db) is op


async def test_non_allowlisted_tenant_admin_refused(db):
    # A self-serve tenant admin — has ADMIN role + MFA, but is not an operator.
    tenant = await make_user(db, email="tenant@customer.com", role=Role.ADMIN, mfa_enabled=True)
    with pytest.raises(HTTPException) as ei:
        await require_plaid_link_access(link_request(plaid_link_allowed_emails=ALLOW), tenant, db)
    assert ei.value.status_code == 403
    assert ei.value.detail["code"] == "PLAID_LINK_NOT_ALLOWLISTED"


async def test_empty_allowlist_is_role_based_public_later(db):
    # Documented "go public" state: empty allow-list => any accountant/admin+MFA.
    admin = await make_user(db, email="tenant@customer.com", role=Role.ADMIN, mfa_enabled=True)
    assert await require_plaid_link_access(link_request(plaid_link_allowed_emails=""), admin, db) is admin


async def test_flag_off_blocks_even_operator(db):
    op = await make_user(db, email="nathano@ocidm.io", role=Role.ADMIN, mfa_enabled=True)
    with pytest.raises(HTTPException) as ei:
        await require_plaid_link_access(
            link_request(plaid_link_enabled=False, plaid_link_allowed_emails=ALLOW), op, db)
    assert ei.value.detail["code"] == "PLAID_LINK_DISABLED"


async def test_operator_without_mfa_refused(db):
    op = await make_user(db, email="nathano@ocidm.io", role=Role.ADMIN, mfa_enabled=False)
    with pytest.raises(HTTPException) as ei:
        await require_plaid_link_access(link_request(plaid_link_allowed_emails=ALLOW), op, db)
    assert ei.value.detail["code"] == "MFA_REQUIRED"


async def test_non_operator_role_refused_even_if_allowlisted(db):
    tm = await make_user(db, email="nathano@ocidm.io", role=Role.TEAM_MEMBER, mfa_enabled=True)
    with pytest.raises(HTTPException) as ei:
        await require_plaid_link_access(link_request(plaid_link_allowed_emails=ALLOW), tm, db)
    assert ei.value.status_code == 403  # role check fires before allow-list


# ---------------------------------------------------------------------------
# Deduplication — manual categorize
# ---------------------------------------------------------------------------


async def test_categorize_flags_duplicate_and_does_not_double_post(db):
    user = await make_user(db, email="op@ocidm.io")
    await make_expense(db, user, amount="50.00", exp_date=D)  # entered by hand
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="50.00", txn_date=D)  # same, from Plaid

    before = await count_expenses(db, user)
    with pytest.raises(PossibleDuplicateError) as ei:
        await plaid_service.categorize_transaction(
            db, txn.id, CategorizeTransactionRequest(as_type="expense", confirm_duplicate=False),
            user, SimpleNamespace(),
        )
    # Carries the candidate(s) for the UI to show.
    assert ei.value.status_code == 409
    assert ei.value.details["possible_duplicates"]
    # No second record was created; the Plaid txn stays uncategorized. (The guard
    # raises before any write, so the session is still usable — no rollback needed.)
    assert await count_expenses(db, user) == before
    is_cat = await db.scalar(
        select(PlaidTransaction.is_categorized).where(PlaidTransaction.id == txn.id)
    )
    assert is_cat is False


async def test_categorize_with_confirm_posts_anyway(db):
    user = await make_user(db, email="op@ocidm.io")
    await make_expense(db, user, amount="50.00", exp_date=D)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="50.00", txn_date=D)

    before = await count_expenses(db, user)
    result = await plaid_service.categorize_transaction(
        db, txn.id, CategorizeTransactionRequest(as_type="expense", confirm_duplicate=True),
        user, SimpleNamespace(),
    )
    assert result.is_categorized is True
    assert await count_expenses(db, user) == before + 1  # user confirmed, so it posts


async def test_categorize_no_match_proceeds(db):
    user = await make_user(db, email="op@ocidm.io")
    await make_expense(db, user, amount="50.00", exp_date=D)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="999.99", txn_date=D)  # different amount

    before = await count_expenses(db, user)
    result = await plaid_service.categorize_transaction(
        db, txn.id, CategorizeTransactionRequest(as_type="expense"), user, SimpleNamespace(),
    )
    assert result.is_categorized is True
    assert await count_expenses(db, user) == before + 1


async def test_income_duplicate_flagged(db):
    user = await make_user(db, email="op@ocidm.io")
    await make_income(db, user, amount="1200.00", inc_date=D)
    conn = await make_connection(db, user)
    txn = await make_txn(db, conn, amount="1200.00", txn_date=D, is_income=True)

    with pytest.raises(PossibleDuplicateError):
        await plaid_service.categorize_transaction(
            db, txn.id, CategorizeTransactionRequest(as_type="income", confirm_duplicate=False),
            user, SimpleNamespace(),
        )


# ---------------------------------------------------------------------------
# Deduplication — automatic rules must SKIP a likely duplicate
# ---------------------------------------------------------------------------


async def test_auto_categorize_skips_duplicate(db):
    from app.accounting.models import ExpenseCategory

    user = await make_user(db, email="op@ocidm.io")
    cat = ExpenseCategory(name="Coffee", created_by=user.id)
    db.add(cat)
    await make_expense(db, user, amount="50.00", exp_date=D)  # manual entry exists
    conn = await make_connection(db, user)
    await db.commit()
    txn = await make_txn(db, conn, amount="50.00", txn_date=D)
    rule = CategorizationRule(
        name="Coffee rule", match_field=MatchField.NAME, match_type=MatchType.CONTAINS,
        match_value="Acme", assign_category_id=cat.id, created_by=user.id, is_active=True,
    )
    db.add(rule)
    await db.commit()

    before = await count_expenses(db, user)
    matched = await apply_rules_to_transaction(db, txn, [rule], user)
    assert matched is False  # skipped — did not auto-post a duplicate
    assert await count_expenses(db, user) == before
    await db.refresh(txn)
    assert txn.is_categorized is False


async def test_auto_categorize_posts_when_no_duplicate(db):
    from app.accounting.models import ExpenseCategory

    user = await make_user(db, email="op@ocidm.io")
    cat = ExpenseCategory(name="Coffee", created_by=user.id)
    db.add(cat)
    conn = await make_connection(db, user)
    await db.commit()
    txn = await make_txn(db, conn, amount="7.25", txn_date=D)  # no manual match
    rule = CategorizationRule(
        name="Coffee rule", match_field=MatchField.NAME, match_type=MatchType.CONTAINS,
        match_value="Acme", assign_category_id=cat.id, created_by=user.id, is_active=True,
    )
    db.add(rule)
    await db.commit()

    matched = await apply_rules_to_transaction(db, txn, [rule], user)
    assert matched is True
    assert await count_expenses(db, user) == 1


# ---------------------------------------------------------------------------
# Matcher unit
# ---------------------------------------------------------------------------


async def test_find_duplicate_records_matches_amount_and_date_window(db):
    user = await make_user(db, email="op@ocidm.io")
    await make_expense(db, user, amount="50.00", exp_date=D)

    assert len(await find_duplicate_records(db, user, amount=Decimal("50.00"), txn_date=D, kind="expense")) == 1
    # within the window
    assert len(await find_duplicate_records(
        db, user, amount=Decimal("50.00"), txn_date=D + timedelta(days=3), kind="expense")) == 1
    # different amount -> no match
    assert await find_duplicate_records(db, user, amount=Decimal("51.00"), txn_date=D, kind="expense") == []
    # outside the date window -> no match
    assert await find_duplicate_records(
        db, user, amount=Decimal("50.00"), txn_date=D + timedelta(days=10), kind="expense") == []
