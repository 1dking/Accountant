"""Password reset flow — token issuance + verification + email send.

Security posture:
- The /request endpoint ALWAYS returns 200 regardless of whether the email
  matches a real user. This prevents account enumeration via response codes.
  TODO: timing-safe response — current code short-circuits on unknown email
  so a side-channel attacker could distinguish "user exists" from "no user"
  by measuring response latency (bcrypt + DB write only fires for real
  hits). Not critical for the admin-only v1 platform; revisit before any
  open-signup rollout.
- Tokens are 64-byte urlsafe (cryptographically random), single-use, and
  expire after 1 hour. On successful confirm we mark used_at + invalidate
  all other live tokens for the user, so a leaked older token can't be
  redeemed.
- Rate limit: 3 reset requests per EMAIL per hour. IP-based limiting is
  unreliable behind Cloudflare + DH's Apache proxy; email-based gating is
  the meaningful axis. The 200-regardless response prevents an attacker
  from using the rate-limit response as an enumeration oracle.
"""
from __future__ import annotations

import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import PasswordResetToken, RefreshToken, User
from app.auth.utils import create_access_token, create_refresh_token, hash_password, hash_token
from app.config import Settings
from app.core.exceptions import RateLimitError, ValidationError

logger = logging.getLogger(__name__)

TOKEN_TTL = timedelta(hours=1)
RESET_RATE_LIMIT = 3
RESET_RATE_WINDOW_SECONDS = 3600  # 1 hour

# In-memory rate-limit store: email -> [timestamps within window]
# Single-process. If we move to multi-worker uvicorn, swap to redis. The
# bound is small (admin-only platform), so a dict is fine for now.
_reset_attempts: dict[str, list[float]] = {}


def _check_email_rate_limit(email: str) -> None:
    """Raise RateLimitError if this email has requested >RESET_RATE_LIMIT
    resets in the last hour. Email-only (not IP+email) because IP is
    unreliable behind Cloudflare/DH proxies."""
    now = time.monotonic()
    cutoff = now - RESET_RATE_WINDOW_SECONDS

    history = _reset_attempts.get(email, [])
    # Drop entries outside the window
    history = [t for t in history if t >= cutoff]

    if len(history) >= RESET_RATE_LIMIT:
        raise RateLimitError(
            "Too many password reset requests for this email. "
            "Please try again later."
        )

    history.append(now)
    _reset_attempts[email] = history


def _generate_token() -> str:
    """64-byte urlsafe token. ~86 chars after base64 — fits in our 128
    VARCHAR with headroom."""
    return secrets.token_urlsafe(64)


async def request_password_reset(
    db: AsyncSession,
    email: str,
    settings: Settings,
) -> None:
    """Issue a reset token if the email maps to an active user, then send
    the reset email. Silently no-ops for unknown emails so the API surface
    never reveals whether an account exists.

    Rate limit (per email, 3/hr) happens BEFORE the user lookup so an
    attacker can't bypass it by churning through email variants — and
    because the limit is per-email, hitting it on a fake address can't be
    used to lock out a real one.
    """
    normalized = email.strip().lower()
    _check_email_rate_limit(normalized)

    result = await db.execute(select(User).where(User.email == normalized))
    user = result.scalar_one_or_none()

    # TODO: timing-safe response. We currently return immediately for
    # unknown emails, which is faster than the real path (DB insert +
    # SMTP send). A patient attacker could distinguish responses by
    # latency. Acceptable for admin-only v1; fix before open signup.
    if user is None or not user.is_active:
        logger.info(
            "password_reset.request unknown_or_inactive email=%s — silent no-op",
            normalized,
        )
        return

    # Mark any existing live tokens for this user as used, so a fresh
    # request supersedes prior ones. Otherwise an attacker who got an
    # older link could redeem it during the 1hr window of a new request.
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc))
    )

    token = _generate_token()
    expires = datetime.now(timezone.utc) + TOKEN_TTL
    record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=token,
        expires_at=expires,
    )
    db.add(record)
    await db.commit()

    # Send email — wrap in try/except so a transient SMTP failure doesn't
    # leak through as a 500. The user already saw 200 from the API; if
    # the email never arrives they can simply request another.
    try:
        await _send_reset_email(db, user, token, settings)
    except Exception as exc:
        logger.exception(
            "password_reset.email_send_failed user_id=%s err=%s",
            user.id, exc,
        )


async def _send_reset_email(
    db: AsyncSession,
    user: User,
    token: str,
    settings: Settings,
) -> None:
    """Render password_reset.html and dispatch via the user's SMTP config
    (falling back to system default). Isolated so the rest of the flow can
    proceed even if SMTP is unconfigured during local dev."""
    from app.email.service import render_template, resolve_smtp_config, send_email

    smtp_config = await resolve_smtp_config(db, user, None)

    reset_url = (
        f"{settings.public_base_url.rstrip('/')}"
        f"/auth/password-reset/confirm/{token}"
    )

    html_body = render_template(
        "password_reset.html",
        user_name=user.full_name or user.email,
        reset_url=reset_url,
        expires_in="1 hour",
        company_name=smtp_config.from_name,
        year=datetime.now(timezone.utc).year,
    )

    await send_email(
        smtp_config,
        to=user.email,
        subject="Reset your password",
        html_body=html_body,
    )


async def confirm_password_reset(
    db: AsyncSession,
    token: str,
    new_password: str,
    settings: Settings,
) -> dict:
    """Validate the token, update the password, and return a fresh
    auth token pair for auto-login. Raises ValidationError for any
    invalid / expired / used token — UI surfaces a single generic
    "this link is no longer valid" message rather than distinguishing
    cases.
    """
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise ValidationError("Invalid or expired reset link.")

    if record.used_at is not None:
        raise ValidationError("This reset link has already been used.")

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise ValidationError("This reset link has expired.")

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise ValidationError("Invalid or expired reset link.")

    user.hashed_password = hash_password(new_password)
    record.used_at = datetime.now(timezone.utc)

    # Invalidate sibling tokens — once you've reset, every other in-flight
    # reset link for this account is dead. Same goes for refresh tokens:
    # a password reset implies "log me out everywhere", so we kill all
    # active sessions and re-issue.
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != record.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc))
    )
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked.is_(False),
        )
        .values(revoked=True)
    )

    # Issue fresh tokens so the user is logged in after redirect.
    access_token = create_access_token(user.id, user.role.value, settings)
    refresh_token = create_refresh_token(user.id, settings)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
    ))

    await db.commit()

    # Fire a password_changed in-app notification so the user gets a
    # visible "your password just changed" entry in the bell — also
    # serves as audit trail.
    try:
        from app.notifications.service import create_notification

        await create_notification(
            db,
            user_id=user.id,
            type="password_changed",
            title="Password changed",
            message=(
                "Your password was reset. If this wasn't you, contact "
                "your administrator immediately."
            ),
            resource_type="user",
            resource_id=str(user.id),
            link_path="/settings?tab=profile",
        )
    except Exception as exc:
        logger.exception(
            "password_reset.notification_failed user_id=%s err=%s",
            user.id, exc,
        )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
