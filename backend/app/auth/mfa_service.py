"""MFA enrollment / verification orchestration.

Wraps the pure TOTP primitives in app/auth/mfa.py with persistence (encrypted
secret + hashed recovery codes on the User), audit logging, and the two-step
login completion. The TOTP secret is stored Fernet-encrypted; recovery codes
only as hashes.
"""

import json
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditAction, AuditResult, safe_record_audit
from app.auth import mfa
from app.auth.models import RefreshToken, User
from app.auth.schemas import TokenResponse
from app.auth.utils import create_access_token, create_refresh_token, hash_token
from app.config import Settings
from app.core.encryption import get_encryption_service
from app.core.exceptions import ForbiddenError, ValidationError

_MFA_PENDING_TTL_MINUTES = 5


# ---------------------------------------------------------------------------
# Pending-login token (issued after password, before TOTP)
# ---------------------------------------------------------------------------

def create_mfa_pending_token(user_id: _uuid.UUID, settings: Settings) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_MFA_PENDING_TTL_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "type": "mfa"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_mfa_pending_token(token: str, settings: Settings) -> _uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "mfa":
            return None
        return _uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError):
        return None


#: Public alias so other second-factor flows (WebAuthn login) can resolve the
#: same pending-login token.
def decode_mfa_pending_token(token: str, settings: Settings) -> _uuid.UUID | None:
    return _decode_mfa_pending_token(token, settings)


async def issue_login_tokens(
    db: AsyncSession, user: User, settings: Settings, *, method: str, ip: str | None = None
) -> TokenResponse:
    """Mint the real session tokens after a second factor is satisfied, and audit
    the successful login. Shared by TOTP, recovery-code, and WebAuthn logins."""
    access_token = create_access_token(user.id, user.role.value, settings)
    refresh_token = create_refresh_token(user.id, settings)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    await db.commit()
    await safe_record_audit(
        db, action=AuditAction.LOGIN_SUCCESS, result=AuditResult.SUCCESS,
        actor_id=user.id, actor_email=user.email, ip_address=ip,
        tenant_id=str(user.org_id) if user.org_id else None,
        metadata={"mfa": True, "method": method},
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

async def start_enrollment(db: AsyncSession, user: User) -> dict:
    """Generate a secret and return the provisioning URI. Not active until
    confirmed. Re-enrolling overwrites any half-finished secret."""
    if user.mfa_enabled:
        raise ValidationError("MFA is already enabled. Disable it first to re-enroll.")

    secret = mfa.generate_secret()
    user.mfa_secret = get_encryption_service().encrypt(secret)
    await db.commit()

    return {
        "secret": secret,
        "otpauth_uri": mfa.provisioning_uri(secret, user.email),
    }


async def confirm_enrollment(db: AsyncSession, user: User, code: str) -> dict:
    """Verify the first TOTP code, flip mfa_enabled on, and mint recovery codes.

    Returns the plaintext recovery codes ONCE — they are only stored hashed.
    """
    if user.mfa_enabled:
        raise ValidationError("MFA is already enabled.")
    if not user.mfa_secret:
        raise ValidationError("Start enrollment first.")

    secret = get_encryption_service().decrypt(user.mfa_secret)
    if not mfa.verify_totp(secret, code):
        await safe_record_audit(
            db, action=AuditAction.MFA_FAILED, result=AuditResult.FAILURE,
            actor_id=user.id, actor_email=user.email, metadata={"stage": "enroll"},
        )
        raise ValidationError("Invalid authenticator code.")

    plain_codes, hashed_codes = mfa.generate_recovery_codes()
    user.mfa_enabled = True
    user.mfa_enrolled_at = datetime.now(timezone.utc)
    user.mfa_recovery_codes = json.dumps(hashed_codes)
    await db.commit()

    await safe_record_audit(
        db, action=AuditAction.MFA_ENROLLED, result=AuditResult.SUCCESS,
        actor_id=user.id, actor_email=user.email,
    )
    return {"recovery_codes": plain_codes}


async def disable_mfa(db: AsyncSession, user: User, code: str) -> None:
    """Turn MFA off. Requires proof of possession (a valid TOTP or recovery code)
    so a hijacked session can't silently strip the second factor."""
    if not user.mfa_enabled:
        raise ValidationError("MFA is not enabled.")

    # Accept a current TOTP or an unused recovery code as proof of possession.
    if not (_verify_second_factor(user, code) or _consume_if_recovery(user, code)):
        await safe_record_audit(
            db, action=AuditAction.MFA_FAILED, result=AuditResult.FAILURE,
            actor_id=user.id, actor_email=user.email, metadata={"stage": "disable"},
        )
        raise ValidationError("Invalid authenticator or recovery code.")

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery_codes = None
    user.mfa_enrolled_at = None
    await db.commit()

    await safe_record_audit(
        db, action=AuditAction.MFA_DISABLED, result=AuditResult.SUCCESS,
        actor_id=user.id, actor_email=user.email,
    )


def get_status(user: User) -> dict:
    remaining = 0
    if user.mfa_recovery_codes:
        try:
            remaining = len(json.loads(user.mfa_recovery_codes))
        except (json.JSONDecodeError, TypeError):
            remaining = 0
    return {
        "mfa_enabled": user.mfa_enabled,
        "enrolled_at": user.mfa_enrolled_at,
        "recovery_codes_remaining": remaining,
    }


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------

def _verify_second_factor(user: User, code: str) -> bool:
    """True if ``code`` is a valid current TOTP. Recovery codes are handled by
    ``_consume_if_recovery`` (they mutate state), so this is TOTP-only."""
    if not user.mfa_secret:
        return False
    secret = get_encryption_service().decrypt(user.mfa_secret)
    return mfa.verify_totp(secret, code)


def _consume_if_recovery(user: User, code: str) -> bool:
    """If ``code`` matches an unused recovery code, consume it (mutates
    user.mfa_recovery_codes) and return True."""
    if not user.mfa_recovery_codes:
        return False
    try:
        hashed = json.loads(user.mfa_recovery_codes)
    except (json.JSONDecodeError, TypeError):
        return False
    remaining = mfa.consume_recovery_code(code, hashed)
    if remaining is None:
        return False
    user.mfa_recovery_codes = json.dumps(remaining)
    return True


# ---------------------------------------------------------------------------
# Two-step login completion
# ---------------------------------------------------------------------------

async def complete_mfa_login(
    db: AsyncSession,
    mfa_token: str,
    code: str,
    settings: Settings,
    ip: str | None = None,
) -> TokenResponse:
    user_id = _decode_mfa_pending_token(mfa_token, settings)
    if user_id is None:
        raise ValidationError("Invalid or expired MFA session. Please log in again.")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active or not user.mfa_enabled:
        raise ValidationError("Invalid or expired MFA session. Please log in again.")

    used_recovery = False
    if _verify_second_factor(user, code):
        ok = True
    elif _consume_if_recovery(user, code):
        ok = True
        used_recovery = True
    else:
        ok = False

    if not ok:
        await safe_record_audit(
            db, action=AuditAction.MFA_FAILED, result=AuditResult.FAILURE,
            actor_id=user.id, actor_email=user.email, ip_address=ip,
            metadata={"stage": "login"},
        )
        raise ValidationError("Invalid authenticator or recovery code.")

    access_token = create_access_token(user.id, user.role.value, settings)
    refresh_token = create_refresh_token(user.id, settings)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    await db.commit()

    if used_recovery:
        await safe_record_audit(
            db, action=AuditAction.MFA_RECOVERY_USED, result=AuditResult.SUCCESS,
            actor_id=user.id, actor_email=user.email, ip_address=ip,
        )
    await safe_record_audit(
        db, action=AuditAction.MFA_VERIFIED, result=AuditResult.SUCCESS,
        actor_id=user.id, actor_email=user.email, ip_address=ip,
    )
    await safe_record_audit(
        db, action=AuditAction.LOGIN_SUCCESS, result=AuditResult.SUCCESS,
        actor_id=user.id, actor_email=user.email, ip_address=ip,
        tenant_id=str(user.org_id) if user.org_id else None,
        metadata={"mfa": True},
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
