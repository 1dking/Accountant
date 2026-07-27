"""User data-rights: export and deletion/anonymization.

Schedule 1 obligations. Two operations:

* ``export_user_data`` — the user's own personal + financial data as JSON, for
  access requests. Never includes secrets (no tokens, no password/mfa secrets).
* ``delete_user_data`` — on a VERIFIED request, hard-delete the user's financial
  + secret child data and irreversibly anonymize the user row.

LEGAL-RETENTION EXCEPTIONS (deliberately NOT deleted; documented here because a
regulator will ask why data survived a deletion request):
  * ``audit_logs``  — security/compliance evidence, incl. the deletion event
    itself. Kept per app/audit/service.py AUDIT_RETENTION_DAYS.
  * ``plaid_consents`` — proof that consent was given/withdrawn. The link to the
    connection is nulled; the record is retained.
  * Financial books (invoices, expenses, ledger entries, tax records) — retained
    for statutory bookkeeping/tax periods. These are the business's records, not
    only the user's PII, and are out of scope of user-initiated erasure.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditAction, AuditResult, safe_record_audit
from app.auth.models import User

logger = logging.getLogger(__name__)


def _serialize(obj, fields: list[str]) -> dict:
    out: dict = {}
    for f in fields:
        val = getattr(obj, f, None)
        if isinstance(val, (datetime,)):
            val = val.isoformat()
        elif isinstance(val, uuid.UUID):
            val = str(val)
        out[f] = val
    return out


async def export_user_data(db: AsyncSession, user: User) -> dict:
    """The user's own personal + financial data. No secrets are included."""
    from app.integrations.plaid.models import (
        PlaidConnection,
        PlaidConsent,
        PlaidTransaction,
    )

    conns = list(
        (
            await db.execute(
                select(PlaidConnection).where(PlaidConnection.user_id == user.id)
            )
        ).scalars().all()
    )
    txns = list(
        (
            await db.execute(
                select(PlaidTransaction)
                .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
                .where(PlaidConnection.user_id == user.id)
            )
        ).scalars().all()
    )
    consents = list(
        (
            await db.execute(
                select(PlaidConsent).where(PlaidConsent.user_id == user.id)
            )
        ).scalars().all()
    )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if user.role else None,
            "auth_provider": user.auth_provider,
            "mfa_enabled": user.mfa_enabled,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "plaid_connections": [
            _serialize(c, ["id", "institution_name", "institution_id", "is_active",
                           "last_sync_at", "created_at"])
            for c in conns
        ],
        "plaid_transactions": [
            _serialize(t, ["id", "plaid_connection_id", "amount", "date", "name",
                           "merchant_name", "category", "is_income", "is_categorized"])
            for t in txns
        ],
        "plaid_consents": [
            _serialize(c, ["id", "product_scope", "consent_version",
                           "privacy_policy_version", "consent_text", "created_at",
                           "revoked_at"])
            for c in consents
        ],
    }


#: (import_path, attr, user-column-attr, label). Child data hard-deleted on
#: erasure. Kept as data (not code) so the set is auditable at a glance.
_DELETION_TARGETS = [
    ("app.integrations.plaid.models", "PlaidConnection", "user_id", "plaid_connections"),
    ("app.integrations.gmail.models", "GmailAccount", "user_id", "gmail_accounts"),
    ("app.integrations.google_calendar.models", "GoogleCalendarAccount", "user_id", "google_calendar_accounts"),
    ("app.email.models", "SmtpConfig", "created_by", "smtp_configs"),
    ("app.auth.models", "RefreshToken", "user_id", "refresh_tokens"),
    ("app.auth.models", "PasswordResetToken", "user_id", "password_reset_tokens"),
]


async def delete_user_data(
    db: AsyncSession,
    user: User,
    *,
    actor: User,
    reason: str | None = None,
    ip: str | None = None,
) -> dict:
    """Hard-delete financial/secret child data and anonymize the user row.

    Idempotent-ish: re-running on an already-anonymized user simply deletes any
    residual child rows again (all no-ops) and returns zero counts.
    """
    import importlib

    summary: dict = {}

    for module_path, class_name, user_col, label in _DELETION_TARGETS:
        try:
            module = importlib.import_module(module_path)
            model = getattr(module, class_name)
            col = getattr(model, user_col)
            # Own transaction per target so one failure can't undo the others.
            res = await db.execute(sa_delete(model).where(col == user.id))
            await db.commit()
            summary[label] = res.rowcount or 0
        except Exception:
            logger.exception("privacy.delete failed for %s", label)
            await db.rollback()
            summary[label] = "error"

    # Anonymize the user row (kept for referential integrity + audit legibility).
    user.email = f"deleted-{user.id.hex[:12]}@deleted.invalid"
    user.full_name = "Deleted User"
    user.hashed_password = None
    user.google_id = None
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery_codes = None
    user.mfa_enrolled_at = None
    user.fallback_phone = None
    user.voicemail_greeting_type = None
    user.voicemail_greeting_storage_key = None
    user.voicemail_greeting_text = None
    user.conversation_template = None
    user.conversation_ai_instructions = None
    user.conversation_reply_enabled = False
    user.booking_link = None
    user.feature_access_json = None
    user.news_preferences_json = None
    user.is_active = False
    user.anonymized_at = datetime.now(timezone.utc)
    await db.commit()

    summary["user"] = "anonymized"
    summary["retained_for_legal_reasons"] = [
        "audit_logs",
        "plaid_consents",
        "financial_books (invoices/expenses/ledger/tax)",
    ]

    await safe_record_audit(
        db,
        action=AuditAction.DATA_DELETED,
        result=AuditResult.SUCCESS,
        actor_id=actor.id,
        actor_email=actor.email,
        resource_type="user",
        resource_id=str(user.id),
        ip_address=ip,
        metadata={"reason": reason, "summary": summary},
    )
    return summary


# ---------------------------------------------------------------------------
# Retention enforcement (scheduler-driven)
# ---------------------------------------------------------------------------


#: Refuse to purge on an implausibly short window. A typo like `3` in
#: PLAID_DATA_RETENTION_DAYS would silently destroy live bank data on the next
#: nightly run, so anything below this is treated as a MISCONFIGURATION and the
#: job declines to delete rather than doing damage. This is a typo guard, not a
#: policy floor — a deliberately short window (data minimization) is legitimate,
#: because Privacy Policy §9 promises 6–7 years for BOOKKEEPING records
#: (expenses/income/invoices, untouched here), while raw Plaid rows are "bank
#: connection data" that §9 deletes on disconnect.
MIN_PLAUSIBLE_RETENTION_DAYS = 30


async def enforce_plaid_retention(db: AsyncSession, retention_days: int) -> int:
    """Age out raw Plaid transaction rows beyond the retention window.

    Scope, matching Privacy Policy §9:
      * Deletes ONLY ``PlaidTransaction`` — the raw bank data retrieved from Plaid.
      * Does NOT touch ``Expense`` / ``Income`` / invoices. Those are the
        bookkeeping records §9 retains for the statutory 6–7 years, and they
        survive independently once a transaction has been categorized.
      * Does NOT touch connections or consent records. Disconnecting a bank
        deletes its transactions immediately via ``ondelete="CASCADE"`` on
        ``PlaidTransaction.plaid_connection_id``; consent rows are retained as
        proof (see the module docstring).

    ``retention_days <= 0`` disables enforcement.
    """
    if retention_days <= 0:
        return 0
    if retention_days < MIN_PLAUSIBLE_RETENTION_DAYS:
        logger.error(
            "plaid_retention REFUSED: retention_days=%d is below the %d-day "
            "plausibility floor and looks like a misconfiguration. No data was "
            "deleted. Set PLAID_DATA_RETENTION_DAYS deliberately or to 0 to disable.",
            retention_days, MIN_PLAUSIBLE_RETENTION_DAYS,
        )
        return 0

    from app.integrations.plaid.models import PlaidTransaction

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    res = await db.execute(
        sa_delete(PlaidTransaction).where(PlaidTransaction.created_at < cutoff)
    )
    await db.commit()
    count = res.rowcount or 0

    if count:
        # Demonstrable: the audit trail shows retention actually ran.
        await safe_record_audit(
            db,
            action=AuditAction.DATA_DELETED,
            result=AuditResult.SUCCESS,
            actor_email="system:retention",
            resource_type="plaid_transactions",
            metadata={
                "reason": "retention_policy",
                "retention_days": retention_days,
                "cutoff": cutoff.isoformat(),
                "rows_deleted": count,
            },
        )
    return count
