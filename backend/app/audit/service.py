"""Write + query helpers for the append-only audit log.

RETENTION: audit rows are retained for AUDIT_RETENTION_DAYS (default 730 days /
2 years) and pruned by the ``prune_audit_logs`` job registered in
app/core/scheduler.py. Two years comfortably covers the "provide records on
request" and access-request windows; tune via the constant below.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog

logger = logging.getLogger(__name__)

#: How long audit rows are kept before the scheduler prunes them.
AUDIT_RETENTION_DAYS = 730


class AuditAction:
    """Canonical action strings. Keep these stable — they are queried on."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"

    MFA_ENROLLED = "mfa_enrolled"
    MFA_VERIFIED = "mfa_verified"
    MFA_FAILED = "mfa_failed"
    MFA_DISABLED = "mfa_disabled"
    MFA_RECOVERY_USED = "mfa_recovery_used"

    WEBAUTHN_REGISTERED = "webauthn_registered"
    WEBAUTHN_AUTHENTICATED = "webauthn_authenticated"
    WEBAUTHN_REMOVED = "webauthn_removed"

    PERMISSION_DENIED = "permission_denied"

    ADMIN_IMPERSONATION = "admin_impersonation"
    FEATURE_FLAG_CHANGED = "feature_flag_changed"
    PRICING_CHANGED = "pricing_changed"

    PLAID_CONSENT_CAPTURED = "plaid_consent_captured"
    PLAID_LINK_TOKEN_CREATED = "plaid_link_token_created"
    PLAID_CONNECTION_CREATED = "plaid_connection_created"

    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"

    # Telephony fraud kill switch — a suspension is a security-relevant event
    # (money + fraud exposure), so both directions are audited with the actor.
    TELEPHONY_SUSPENDED = "telephony_suspended"
    TELEPHONY_REACTIVATED = "telephony_reactivated"

    # De-provisioning — a departure or role change revokes access across systems
    # in one audited action. See app/platform_admin/deprovision.py.
    USER_DEPROVISIONED = "user_deprovisioned"
    USER_ACCESS_TRANSFERRED = "user_access_transferred"


class AuditResult:
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    result: str = AuditResult.SUCCESS,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    tenant_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
    commit: bool = False,
) -> AuditLog:
    """Append one audit row.

    ``commit=False`` (default) flushes into the caller's transaction so the audit
    row lands atomically with whatever the caller is doing. ``commit=True`` for
    standalone events (e.g. a login failure, which has no other write).
    """
    entry = AuditLog(
        action=action,
        result=result,
        actor_id=actor_id,
        actor_email=actor_email,
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        metadata_json=json.dumps(metadata, default=str) if metadata else None,
    )
    db.add(entry)
    if commit:
        await db.commit()
    else:
        await db.flush()
    return entry


async def safe_record_audit(db: AsyncSession, **kwargs) -> None:
    """Fire-and-forget audit write that never propagates an error.

    For call sites where a failed audit write must not break the user-facing
    action. Rolls back its own partial state on error so the caller's session
    stays usable.
    """
    try:
        await record_audit(db, commit=True, **kwargs)
    except Exception:
        logger.warning("audit write failed action=%s", kwargs.get("action"), exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass


async def list_audit(
    db: AsyncSession,
    *,
    action: str | None = None,
    result: str | None = None,
    actor_id: uuid.UUID | None = None,
    tenant_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """Paginated, filtered audit query, newest first."""
    base = select(AuditLog)
    count_base = select(func.count(AuditLog.id))

    conds = []
    if action:
        conds.append(AuditLog.action == action)
    if result:
        conds.append(AuditLog.result == result)
    if actor_id:
        conds.append(AuditLog.actor_id == actor_id)
    if tenant_id:
        conds.append(AuditLog.tenant_id == tenant_id)
    for c in conds:
        base = base.where(c)
        count_base = count_base.where(c)

    total = (await db.execute(count_base)).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def prune_audit_logs(db: AsyncSession, retention_days: int = AUDIT_RETENTION_DAYS) -> int:
    """Delete audit rows older than the retention window. Returns rows removed."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await db.execute(sa_delete(AuditLog).where(AuditLog.created_at < cutoff))
    await db.commit()
    return result.rowcount or 0
