"""Data export + deletion/anonymization + Plaid retention enforcement."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.audit.models import AuditLog
from app.audit.service import AuditAction
from app.auth.models import RefreshToken, User
from app.core import legal
from app.core.encryption import init_encryption_service
from app.integrations.plaid.models import PlaidConnection, PlaidConsent, PlaidTransaction
from app.privacy import service
from tests.conftest import auth_header

init_encryption_service("")


async def _seed_bank_data(db, user, *, txn_age_days: int = 1) -> PlaidConnection:
    conn = PlaidConnection(
        user_id=user.id,
        institution_name="Seed Bank",
        institution_id="ins_seed",
        encrypted_access_token="enc-token",
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
        amount=Decimal("12.34"),
        date=date.today(),
        name="Coffee",
        created_at=datetime.now(timezone.utc) - timedelta(days=txn_age_days),
    ))
    await db.commit()
    return conn


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_returns_data_without_secrets(client, team_member_user, db):
    await _seed_bank_data(db, team_member_user)

    r = await client.post("/api/privacy/me/export", headers=auth_header(team_member_user))
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert data["profile"]["email"] == team_member_user.email
    assert len(data["plaid_connections"]) == 1
    assert len(data["plaid_transactions"]) == 1
    assert len(data["plaid_consents"]) == 1

    # No secrets leak into the export.
    assert "hashed_password" not in data["profile"]
    assert "mfa_secret" not in data["profile"]
    assert "encrypted_access_token" not in data["plaid_connections"][0]


# ---------------------------------------------------------------------------
# Deletion / anonymization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_requires_confirmation(client, team_member_user, db):
    r = await client.post(
        "/api/privacy/me/delete", headers=auth_header(team_member_user), json={"confirm": "nope"}
    )
    assert r.status_code == 400
    await db.refresh(team_member_user)
    assert team_member_user.anonymized_at is None


@pytest.mark.asyncio
async def test_delete_anonymizes_user_and_removes_financial_data(client, team_member_user, db):
    conn = await _seed_bank_data(db, team_member_user)
    db.add(RefreshToken(
        user_id=team_member_user.id,
        token_hash=f"hash-{uuid.uuid4().hex}",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    ))
    await db.commit()
    original_email = team_member_user.email

    r = await client.post(
        "/api/privacy/me/delete",
        headers=auth_header(team_member_user),
        json={"confirm": "DELETE", "reason": "user request"},
    )
    assert r.status_code == 200, r.text

    await db.refresh(team_member_user)
    # User anonymized, not left intact.
    assert team_member_user.anonymized_at is not None
    assert team_member_user.email != original_email
    assert team_member_user.email.endswith("@deleted.invalid")
    assert team_member_user.is_active is False
    assert team_member_user.hashed_password is None

    # Financial + secret child data hard-deleted.
    conns = (await db.execute(
        select(func.count(PlaidConnection.id)).where(PlaidConnection.user_id == team_member_user.id)
    )).scalar()
    assert conns == 0
    txns = (await db.execute(select(func.count(PlaidTransaction.id)))).scalar()
    assert txns == 0  # cascaded with the connection
    tokens = (await db.execute(
        select(func.count(RefreshToken.id)).where(RefreshToken.user_id == team_member_user.id)
    )).scalar()
    assert tokens == 0

    # Consent RETAINED as legal proof (connection link nulled).
    consent = (await db.execute(select(PlaidConsent))).scalar_one()
    assert consent.connection_id is None


@pytest.mark.asyncio
async def test_delete_is_audited(client, team_member_user, db):
    await client.post(
        "/api/privacy/me/delete", headers=auth_header(team_member_user), json={"confirm": "DELETE"}
    )
    actions = (await db.execute(select(AuditLog.action))).scalars().all()
    assert AuditAction.DATA_DELETED in actions


@pytest.mark.asyncio
async def test_admin_can_export_another_user(client, admin_user, team_member_user, db):
    await _seed_bank_data(db, team_member_user)
    r = await client.get(
        f"/api/privacy/admin/users/{team_member_user.id}/export", headers=auth_header(admin_user)
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["profile"]["email"] == team_member_user.email


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retention_prunes_old_transactions_only(db, team_member_user):
    await _seed_bank_data(db, team_member_user, txn_age_days=400)  # old
    await _seed_bank_data(db, team_member_user, txn_age_days=1)    # recent

    # Disabled by default: nothing pruned.
    assert await service.enforce_plaid_retention(db, 0) == 0
    assert (await db.execute(select(func.count(PlaidTransaction.id)))).scalar() == 2

    # 365-day window removes the 400-day-old row only.
    removed = await service.enforce_plaid_retention(db, 365)
    assert removed == 1
    assert (await db.execute(select(func.count(PlaidTransaction.id)))).scalar() == 1
