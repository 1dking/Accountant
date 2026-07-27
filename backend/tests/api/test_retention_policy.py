"""Privacy Policy §9 retention promises, enforced rather than documented.

The promises being tested:
  * raw Plaid bank rows age out on the configured window;
  * disconnecting a bank deletes that connection's transaction data immediately;
  * the derived BOOKKEEPING records (expenses/income) survive the purge, because
    §9 retains those for the statutory 6-7 years;
  * consent evidence survives;
  * an implausibly short window is refused instead of destroying live data.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.accounting.models import Expense
from app.core import legal
from app.core.encryption import init_encryption_service
from app.integrations.plaid.models import PlaidConnection, PlaidConsent, PlaidTransaction
from app.privacy.service import MIN_PLAUSIBLE_RETENTION_DAYS, enforce_plaid_retention

init_encryption_service("")


async def _seed(db, user, *, age_days: int) -> PlaidConnection:
    conn = PlaidConnection(
        user_id=user.id,
        institution_name="Seed Bank",
        institution_id="ins_seed",
        encrypted_access_token="enc",
        item_id=f"item-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(conn)
    await db.flush()
    db.add(PlaidConsent(
        user_id=user.id,
        product_scope=legal.PLAID_PRODUCT_SCOPE,
        consent_version=legal.PLAID_CONSENT_VERSION,
        privacy_policy_version=legal.PRIVACY_POLICY_VERSION,
        consent_text=legal.PLAID_CONSENT_TEXT,
        connection_id=conn.id,
    ))
    db.add(PlaidTransaction(
        plaid_connection_id=conn.id,
        plaid_transaction_id=f"txn-{uuid.uuid4().hex[:8]}",
        account_id="a1",
        amount=Decimal("25.00"),
        date=date.today(),
        name="Groceries",
        created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    ))
    await db.commit()
    return conn


@pytest.mark.asyncio
async def test_default_window_is_active_and_matches_the_policy(app):
    """The job must actually be ON — documented-only retention was the gap."""
    days = app.state.settings.plaid_data_retention_days
    assert days > 0, "retention is disabled; §9 would be documented but unenforced"
    assert days >= 2190, f"{days}d is under the 6-year floor §9 commits to"
    assert days <= 2555, f"{days}d exceeds the 7-year outer bound in §9"


@pytest.mark.asyncio
async def test_rows_inside_the_window_are_kept(db, team_member_user):
    await _seed(db, team_member_user, age_days=100)
    assert await enforce_plaid_retention(db, 2555) == 0
    assert (await db.execute(select(func.count(PlaidTransaction.id)))).scalar() == 1


@pytest.mark.asyncio
async def test_rows_beyond_the_window_are_purged(db, team_member_user):
    await _seed(db, team_member_user, age_days=3000)  # ~8 years
    assert await enforce_plaid_retention(db, 2555) == 1
    assert (await db.execute(select(func.count(PlaidTransaction.id)))).scalar() == 0


@pytest.mark.asyncio
async def test_purge_keeps_bookkeeping_records_and_consent(db, team_member_user):
    """§9 keeps financial/bookkeeping records for the statutory period. Ageing out
    a raw bank row must not take the expense it produced — or the consent."""
    await _seed(db, team_member_user, age_days=3000)
    db.add(Expense(
        user_id=team_member_user.id,
        vendor_name="Seed Bank",
        description="Groceries",
        amount=Decimal("25.00"),
        currency="USD",
        date=date.today(),
    ))
    await db.commit()

    assert await enforce_plaid_retention(db, 2555) == 1

    assert (await db.execute(select(func.count(Expense.id)))).scalar() == 1, \
        "retention deleted a bookkeeping record §9 promises to keep"
    assert (await db.execute(select(func.count(PlaidConsent.id)))).scalar() == 1, \
        "retention deleted consent evidence"


@pytest.mark.asyncio
async def test_disconnecting_a_bank_deletes_its_transactions_now(db, team_member_user):
    """§9: bank connection data is deleted when you disconnect — not on a timer."""
    from app.integrations.plaid import service as plaid_service

    conn = await _seed(db, team_member_user, age_days=1)
    assert (await db.execute(select(func.count(PlaidTransaction.id)))).scalar() == 1

    await plaid_service.delete_connection(db, conn.id, team_member_user.id)

    assert (await db.execute(select(func.count(PlaidTransaction.id)))).scalar() == 0, \
        "disconnect left bank transaction data behind"
    # Consent is retained as proof, with the connection link nulled.
    consent = (await db.execute(select(PlaidConsent))).scalar_one()
    assert consent.connection_id is None


@pytest.mark.asyncio
async def test_implausibly_short_window_is_refused(db, team_member_user):
    """A typo must not silently wipe live bank data on the nightly run."""
    await _seed(db, team_member_user, age_days=100)
    removed = await enforce_plaid_retention(db, MIN_PLAUSIBLE_RETENTION_DAYS - 1)
    assert removed == 0
    assert (await db.execute(select(func.count(PlaidTransaction.id)))).scalar() == 1, \
        "a misconfigured window deleted live data"


@pytest.mark.asyncio
async def test_zero_disables_enforcement(db, team_member_user):
    await _seed(db, team_member_user, age_days=3000)
    assert await enforce_plaid_retention(db, 0) == 0
    assert (await db.execute(select(func.count(PlaidTransaction.id)))).scalar() == 1
