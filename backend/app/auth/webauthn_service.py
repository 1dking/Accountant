"""WebAuthn / passkey ceremonies (registration + authentication).

All cryptographic verification is delegated to the maintained ``webauthn``
(py_webauthn) library — no custom crypto here. This module owns: challenge
bookkeeping, credential persistence, the sign-count replay check (the relying
party's responsibility), and audit logging.

RP ID / origin come from Settings (config-driven) so production uses the real
deployed domain — see app/config.py webauthn_* fields.
"""

import json
import logging
import time
import uuid

import webauthn
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditAction, AuditResult, safe_record_audit
from app.auth.models import User
from app.auth.webauthn_models import WebAuthnCredential
from app.config import Settings
from app.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

# In-memory challenge store, keyed by f"{purpose}:{user_id}". Matches the
# existing in-process pattern (OAuth state, login rate-limit) — fine for the
# single-worker VPS. A challenge is single-use and short-lived.
_CHALLENGE_TTL_SECONDS = 300
_challenges: dict[str, tuple[bytes, float]] = {}


def _put_challenge(key: str, challenge: bytes) -> None:
    _challenges[key] = (challenge, time.monotonic() + _CHALLENGE_TTL_SECONDS)


def _take_challenge(key: str) -> bytes | None:
    entry = _challenges.pop(key, None)
    if entry is None:
        return None
    challenge, expiry = entry
    if time.monotonic() > expiry:
        return None
    return challenge


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def begin_registration(db: AsyncSession, user: User, settings: Settings) -> dict:
    """Issue registration options. Excludes already-registered credentials so a
    device can't be enrolled twice."""
    existing = list(
        (
            await db.execute(
                select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
            )
        ).scalars().all()
    )
    exclude = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id)) for c in existing
    ]

    options = webauthn.generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.full_name or user.email,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    _put_challenge(f"reg:{user.id}", options.challenge)
    return json.loads(webauthn.options_to_json(options))


async def finish_registration(
    db: AsyncSession, user: User, credential: dict, device_name: str | None, settings: Settings
) -> WebAuthnCredential:
    """Verify the attestation and persist the new credential (public key only)."""
    challenge = _take_challenge(f"reg:{user.id}")
    if challenge is None:
        raise ValidationError("Registration challenge expired or missing. Please try again.")

    try:
        verification = webauthn.verify_registration_response(
            credential=json.dumps(credential),
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            require_user_verification=False,
        )
    except Exception as exc:  # library raises InvalidRegistrationResponse
        logger.warning(
            "webauthn.registration_verify_failed rp_id=%s expected_origin=%s err=%r",
            settings.webauthn_rp_id, settings.webauthn_origin, exc,
        )
        raise ValidationError(f"Passkey registration could not be verified: {str(exc)[:160]}")

    credential_id_b64 = bytes_to_base64url(verification.credential_id)

    existing = (
        await db.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.credential_id == credential_id_b64
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValidationError("This passkey is already registered.")

    transports = None
    try:
        t = credential.get("response", {}).get("transports")
        if t:
            transports = json.dumps(t)[:255]
    except (AttributeError, TypeError):
        transports = None

    row = WebAuthnCredential(
        user_id=user.id,
        credential_id=credential_id_b64,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=transports,
        attestation_fmt=str(getattr(verification, "fmt", "") or "")[:50] or None,
        device_name=(device_name or "Passkey").strip()[:100] or "Passkey",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    await safe_record_audit(
        db,
        action=AuditAction.WEBAUTHN_REGISTERED,
        result=AuditResult.SUCCESS,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="webauthn_credential",
        resource_id=str(row.id),
        metadata={"device_name": row.device_name},
    )
    return row


# ---------------------------------------------------------------------------
# Authentication (assertion)
# ---------------------------------------------------------------------------

async def begin_authentication(db: AsyncSession, user: User, settings: Settings) -> dict:
    creds = list(
        (
            await db.execute(
                select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
            )
        ).scalars().all()
    )
    if not creds:
        raise ValidationError("No passkeys are registered for this account.")

    allow = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id)) for c in creds]
    options = webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _put_challenge(f"auth:{user.id}", options.challenge)
    return json.loads(webauthn.options_to_json(options))


async def verify_authentication(
    db: AsyncSession, user: User, credential: dict, settings: Settings, ip: str | None = None
) -> WebAuthnCredential:
    """Verify an assertion and enforce the sign-count increase (clone detection)."""
    challenge = _take_challenge(f"auth:{user.id}")
    if challenge is None:
        raise ValidationError("Authentication challenge expired or missing. Please try again.")

    credential_id_b64 = credential.get("id") or credential.get("rawId")
    row = (
        await db.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.credential_id == credential_id_b64,
                WebAuthnCredential.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValidationError("Unrecognized passkey.")

    try:
        verification = webauthn.verify_authentication_response(
            credential=json.dumps(credential),
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=row.public_key,
            credential_current_sign_count=row.sign_count,
            require_user_verification=False,
        )
    except Exception as exc:  # InvalidAuthenticationResponse
        await safe_record_audit(
            db, action=AuditAction.MFA_FAILED, result=AuditResult.FAILURE,
            actor_id=user.id, actor_email=user.email, ip_address=ip,
            metadata={"factor": "webauthn", "reason": "verify_failed"},
        )
        raise ValidationError(f"Passkey assertion could not be verified: {str(exc)[:160]}")

    # Cloned-authenticator detection: if either counter is non-zero, the new
    # counter MUST be strictly greater than the stored one. (Both zero means the
    # authenticator doesn't implement a counter — allowed.)
    new_count = verification.new_sign_count
    if (new_count != 0 or row.sign_count != 0) and new_count <= row.sign_count:
        await safe_record_audit(
            db, action=AuditAction.WEBAUTHN_AUTHENTICATED, result=AuditResult.FAILURE,
            actor_id=user.id, actor_email=user.email, ip_address=ip,
            resource_type="webauthn_credential", resource_id=str(row.id),
            metadata={"reason": "sign_count_not_increased", "stored": row.sign_count, "received": new_count},
        )
        raise ValidationError(
            "Passkey signature counter did not increase — possible cloned authenticator. "
            "This passkey has been rejected."
        )

    from datetime import datetime, timezone

    row.sign_count = new_count
    row.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    await safe_record_audit(
        db, action=AuditAction.WEBAUTHN_AUTHENTICATED, result=AuditResult.SUCCESS,
        actor_id=user.id, actor_email=user.email, ip_address=ip,
        resource_type="webauthn_credential", resource_id=str(row.id),
    )
    return row


# ---------------------------------------------------------------------------
# Management
# ---------------------------------------------------------------------------

async def list_credentials(db: AsyncSession, user_id: uuid.UUID) -> list[WebAuthnCredential]:
    return list(
        (
            await db.execute(
                select(WebAuthnCredential)
                .where(WebAuthnCredential.user_id == user_id)
                .order_by(WebAuthnCredential.created_at.desc())
            )
        ).scalars().all()
    )


async def remove_credential(db: AsyncSession, user: User, credential_pk: uuid.UUID) -> None:
    row = (
        await db.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.id == credential_pk,
                WebAuthnCredential.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        # 404, not 403 — don't reveal whether the id exists on another account.
        raise NotFoundError("Passkey", str(credential_pk))
    await db.delete(row)
    await db.commit()

    await safe_record_audit(
        db,
        action=AuditAction.WEBAUTHN_REMOVED,
        result=AuditResult.SUCCESS,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="webauthn_credential",
        resource_id=str(credential_pk),
    )
