"""Password reset flow — token lifecycle + enumeration resistance.

Live SMTP is mocked out: `_send_reset_email` is the only call site that
hits aiosmtplib, so we patch it to a no-op. We're testing the token
state machine + endpoint contract, not the email transport (covered by
the email service's own tests).
"""
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import PasswordResetToken, User
from app.auth.utils import hash_password, verify_password


@pytest_asyncio.fixture(autouse=True)
async def _mock_send_email(monkeypatch):
    """Stub the SMTP send so tests don't try to dial out.

    We patch the inner `_send_reset_email` rather than `send_email`
    itself, which keeps the test surface tight to the password_reset
    module without bleeding into other email-sending code paths.
    """
    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.auth.password_reset._send_reset_email", _noop
    )
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limit_store():
    """Each test gets a clean rate-limit dict. The store is module-level
    state, so without this a single hot test could exhaust the budget
    and trip the next one."""
    from app.auth import password_reset

    password_reset._reset_attempts.clear()
    yield
    password_reset._reset_attempts.clear()


@pytest.mark.high
class TestRequestEndpoint:
    async def test_unknown_email_returns_200_no_token(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Unknown email must yield the same 200 + generic message as a
        real hit, with NO token persisted. This is the enumeration guard."""
        resp = await client.post(
            "/api/auth/password-reset/request",
            json={"email": "nobody@nowhere.example.com"},
        )
        assert resp.status_code == 200
        assert "reset link has been sent" in resp.json()["data"]["message"]

        # And critically — no token row was created.
        rows = await db.execute(select(PasswordResetToken))
        assert list(rows.scalars().all()) == []

    async def test_real_user_gets_token_persisted(
        self, client: AsyncClient, db: AsyncSession, admin_user: User
    ):
        resp = await client.post(
            "/api/auth/password-reset/request",
            json={"email": admin_user.email},
        )
        assert resp.status_code == 200

        rows = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == admin_user.id
            )
        )
        tokens = list(rows.scalars().all())
        assert len(tokens) == 1
        # Token should be a non-empty urlsafe string with a future expiry.
        t = tokens[0]
        assert t.token and len(t.token) >= 40
        assert t.used_at is None
        exp = t.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        assert exp > datetime.now(timezone.utc)


@pytest.mark.high
class TestConfirmEndpoint:
    async def test_expired_token_rejected(
        self, client: AsyncClient, db: AsyncSession, admin_user: User
    ):
        """An expired token must not let anyone change the password,
        even if it was never used. 1hr TTL is the only knob protecting
        a leaked link from indefinite reuse."""
        import uuid

        record = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            token="expired-token-fixture-xyz",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(record)
        await db.commit()

        resp = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "expired-token-fixture-xyz", "new_password": "NewPass123!"},
        )
        assert resp.status_code == 422
        # Password unchanged
        await db.refresh(admin_user)
        assert verify_password("TestPass123!", admin_user.hashed_password)

    async def test_single_use_token(
        self, client: AsyncClient, db: AsyncSession, admin_user: User
    ):
        """Once a token has redeemed a reset, a second attempt with the
        same token must fail. Otherwise an attacker who later sees the
        URL in a logged email could replay it."""
        import uuid

        record = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            token="single-use-token-fixture",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(record)
        await db.commit()

        ok = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "single-use-token-fixture", "new_password": "FirstPass123!"},
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()["data"]
        assert body["access_token"]
        assert body["refresh_token"]

        # Replay — must fail.
        replay = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "single-use-token-fixture", "new_password": "SecondPass456!"},
        )
        assert replay.status_code == 422

        # Verify the FIRST password stuck and the SECOND never wrote.
        await db.refresh(admin_user)
        assert verify_password("FirstPass123!", admin_user.hashed_password)
        assert not verify_password("SecondPass456!", admin_user.hashed_password)

    async def test_invalidates_other_live_tokens(
        self, client: AsyncClient, db: AsyncSession, admin_user: User
    ):
        """If a user requests two resets in a row (e.g. didn't see the
        first email), redeeming either should kill the other. Otherwise
        a previously-leaked link stays live for an hour after a fresh
        reset is issued."""
        import uuid

        token_old = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            token="older-token-fixture",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        token_new = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            token="newer-token-fixture",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(token_old)
        db.add(token_new)
        await db.commit()

        # Redeem the newer one
        resp = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "newer-token-fixture", "new_password": "Reset123!"},
        )
        assert resp.status_code == 200, resp.text

        # The older token must now be unusable.
        replay = await client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "older-token-fixture", "new_password": "Other999!"},
        )
        assert replay.status_code == 422


@pytest.mark.normal
class TestRateLimit:
    async def test_rate_limit_kicks_in_after_three(
        self, client: AsyncClient, admin_user: User
    ):
        """Email-scoped rate limit: 3 requests per email per hour, then
        the 4th is rejected with 429. Documenting the threshold here so
        a future tweak doesn't silently relax it."""
        for _ in range(3):
            ok = await client.post(
                "/api/auth/password-reset/request",
                json={"email": admin_user.email},
            )
            assert ok.status_code == 200

        capped = await client.post(
            "/api/auth/password-reset/request",
            json={"email": admin_user.email},
        )
        assert capped.status_code == 429
