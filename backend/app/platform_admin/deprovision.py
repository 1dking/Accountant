"""One audited action to revoke a departing/transferred user's access.

Small team, no HR system to integrate against. This module is the single choke
point so that "remove this person" or "change this person's role" can't miss a
system: everything it CAN revoke through an API, it revokes; everything it
can't, it emits as a dated manual checklist the operator must complete.

Operator-only — exposed through ``require_platform_admin`` endpoints in
``app/platform_admin/router.py`` and the ``scripts/deprovision_user.py`` CLI.
Every run writes a ``security_audit_logs`` row (who, whom, when, what was
revoked). See DEPROVISIONING.md.

Automated here:
  * deactivate the O-Brain account (``is_active = False``) — blocks login,
  * revoke ALL active sessions (reuses ``revoke_all_user_sessions``),
  * revoke MFA/TOTP and delete all passkeys (WebAuthn credentials),
  * downgrade role to VIEWER and clear feature access (de-provision), or set the
    new role/features (transfer),
  * revoke every telephony capability grant on the tenant's subaccount,
  * remove the user as a GitHub repo collaborator (if configured).

Surfaced as a manual checklist (can't be done from here):
  * SSH key removal on the VPS, DreamHost panel, Twilio/Plaid/Stripe console
    seats, and removing the email from any .env allow-list
    (TELEPHONY_EXEMPT_EMAILS / SUPER_ADMIN_EMAILS) — env config, not runtime.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditAction, AuditResult, record_audit
from app.auth.models import Role, User
from app.auth.webauthn_models import WebAuthnCredential
from app.billing.ai_meter import tenant_key_for
from app.billing.models import TelephonyAccount
from app.core.exceptions import NotFoundError, ValidationError
from app.integrations.github.client import parse_repos, remove_collaborator
from app.platform_admin.service import revoke_all_user_sessions

logger = logging.getLogger(__name__)

#: Every operator-grantable telephony capability. De-provision/transfer clears
#: all of them (least privilege — the operator re-grants explicitly if needed).
TELEPHONY_CAP_FIELDS = (
    "allow_voice_outbound",
    "allow_voice_inbound",
    "allow_sms",
    "allow_mms",
    "allow_number_purchase",
    "allow_markup",
)


# ---------------------------------------------------------------------------
# Lookups + guards
# ---------------------------------------------------------------------------


async def resolve_user(db: AsyncSession, identifier: str) -> User:
    """Find the target by user-id (UUID) or email. Raises NotFoundError."""
    ident = str(identifier).strip()
    try:
        uid = uuid.UUID(ident)
        row = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    except (ValueError, AttributeError):
        row = (
            await db.execute(select(User).where(User.email == ident))
        ).scalar_one_or_none()
        if row is None:  # tolerate case differences on email
            row = (
                await db.execute(
                    select(User).where(User.email.ilike(ident))
                )
            ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("User", ident)
    return row


def _guard(target: User, actor: User) -> None:
    if actor is not None and target.id == actor.id:
        raise ValidationError(
            "You cannot de-provision or transfer your own account. "
            "Ask another operator to do it."
        )


def _super_admin_emails(settings) -> set[str]:
    raw = getattr(settings, "super_admin_emails", "") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _is_operator(user: User, settings) -> bool:
    """Same definition as ``require_platform_admin``: an operator is an ADMIN by
    role OR an email in SUPER_ADMIN_EMAILS. (Only ACTIVE users can actually
    authenticate as one — deactivation locks them out.)"""
    return user.role == Role.ADMIN or (user.email or "").lower() in _super_admin_emails(settings)


async def _count_other_active_operators(db: AsyncSession, target: User, settings) -> int:
    """How many ACTIVE operators exist besides ``target``."""
    supers = _super_admin_emails(settings)
    rows = (
        await db.execute(
            select(User).where(User.is_active.is_(True), User.id != target.id)
        )
    ).scalars().all()
    return sum(
        1 for u in rows
        if u.role == Role.ADMIN or (u.email or "").lower() in supers
    )


async def _ensure_not_last_operator(
    db: AsyncSession, target: User, settings, *, target_stays_operator: bool
) -> None:
    """Refuse if this action would leave ZERO active operators.

    Independent of who the actor is — a second line of defence behind the
    self-guard and the endpoint/CLI operator gate. If the target is currently an
    operator, will NOT remain one after this action, and no other active operator
    exists, we refuse. This is what makes "the last/sole operator cannot be
    de-provisioned (or downgraded)" a hard invariant rather than an accident of
    the self-guard.
    """
    if target_stays_operator or not _is_operator(target, settings):
        return
    if await _count_other_active_operators(db, target, settings) == 0:
        raise ValidationError(
            f"Refusing: {target.email} is the last active operator "
            "(admin / super-admin). Promote or add another operator first, "
            "then retry — you cannot leave the platform with no administrator."
        )


def _in_env_list(email: str, raw: str | None) -> bool:
    entries = {e.strip().lower() for e in (raw or "").split(",") if e.strip()}
    return bool(entries) and (email or "").lower() in entries


# ---------------------------------------------------------------------------
# Revocation primitives (shared by de-provision AND transfer — one audited path)
# ---------------------------------------------------------------------------


async def _revoke_mfa_and_passkeys(db: AsyncSession, user: User) -> dict:
    """Clear TOTP secret/recovery + delete all passkeys for the user."""
    had_mfa = bool(user.mfa_enabled or user.mfa_secret)
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery_codes = None
    user.mfa_enrolled_at = None
    result = await db.execute(
        delete(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
    )
    return {"mfa_disabled": had_mfa, "passkeys_removed": int(result.rowcount or 0)}


async def _revoke_telephony_capabilities(db: AsyncSession, user: User, actor: User) -> dict:
    """Turn OFF every capability grant on the user's telephony subaccount."""
    tenant = tenant_key_for(user)
    account = (
        await db.execute(
            select(TelephonyAccount).where(TelephonyAccount.tenant_key == tenant)
        )
    ).scalar_one_or_none()
    if account is None:
        return {"tenant_key": tenant, "account": False, "revoked": []}

    revoked: list[str] = []
    for field in TELEPHONY_CAP_FIELDS:
        if getattr(account, field, False):
            setattr(account, field, False)
            revoked.append(field)
    if revoked:
        account.capabilities_updated_by = actor.id if actor else None
        account.capabilities_updated_at = datetime.now(timezone.utc)
    return {"tenant_key": tenant, "account": True, "revoked": revoked}


async def _remove_from_github(settings, github_username: str | None) -> dict:
    """Best-effort GitHub collaborator removal across all configured repos."""
    repos = parse_repos(getattr(settings, "github_repos", ""))
    token = getattr(settings, "github_token", "") or ""
    if not github_username:
        return {"attempted": False, "reason": "no github_username supplied", "repos": []}
    if not token or not repos:
        return {"attempted": False, "reason": "github_token/github_repos not configured", "repos": []}

    api_base = getattr(settings, "github_api_base", "https://api.github.com")
    results = []
    for repo in repos:
        results.append(await remove_collaborator(token, repo, github_username, api_base=api_base))
    return {"attempted": True, "username": github_username, "repos": results}


def _privileged_list_warnings(email: str, settings) -> list[str]:
    """Env allow-lists can't be edited at runtime — surface them as warnings."""
    warnings: list[str] = []
    if _in_env_list(email, getattr(settings, "telephony_exempt_emails", "")):
        warnings.append(
            f"{email} is in TELEPHONY_EXEMPT_EMAILS (bypasses telephony billing/limits) — "
            "remove it from the server .env and restart the backend."
        )
    if _in_env_list(email, getattr(settings, "super_admin_emails", "")):
        warnings.append(
            f"{email} is in SUPER_ADMIN_EMAILS (platform-admin access regardless of role) — "
            "remove it from the server .env and restart the backend."
        )
    return warnings


# ---------------------------------------------------------------------------
# Manual checklist
# ---------------------------------------------------------------------------


def build_manual_checklist(
    *,
    target_email: str,
    actor_email: str,
    when: datetime,
    is_transfer: bool,
    github: dict,
    extra_warnings: list[str],
) -> str:
    """A dated markdown checklist of the steps this action could NOT automate."""
    date = when.strftime("%Y-%m-%d %H:%M UTC")
    title = "Role change" if is_transfer else "De-provision"
    lines = [
        f"# {title} manual checklist — {target_email}",
        f"_Generated {date} by {actor_email}. Complete every unchecked item._",
        "",
    ]

    # Env allow-lists (detected) come first — they are the sharpest gaps.
    for w in extra_warnings:
        lines.append(f"- [ ] **{w}**")

    if not is_transfer:
        # Systems with no API in our control.
        lines += [
            f"- [ ] Remove `{target_email}`'s SSH public key from the VPS "
            "(`~/.ssh/authorized_keys` for every shell account they could reach).",
            "- [ ] DreamHost panel: remove the user / revoke any shared panel access.",
            "- [ ] Twilio Console: remove their seat / rotate any credentials they held.",
            "- [ ] Plaid Dashboard: remove their team seat.",
            "- [ ] Stripe Dashboard: remove their team member seat.",
            "- [ ] Rotate any shared secrets this person knew "
            "(API keys, `.env` values) if their departure warrants it.",
        ]
    else:
        lines += [
            "- [ ] Re-grant only the telephony capabilities appropriate to the NEW role "
            "(all were revoked; nothing is assumed).",
            "- [ ] Review console seats (Twilio/Plaid/Stripe/DreamHost) and adjust to the new role.",
        ]

    # GitHub: reflect what happened, or flag it if we couldn't do it.
    if github.get("attempted"):
        failures = [r for r in github.get("repos", []) if r.get("status") == "error"]
        if failures:
            for r in failures:
                lines.append(
                    f"- [ ] GitHub: removal FAILED on `{r['repo']}` "
                    f"({r.get('detail')}) — remove `{github.get('username')}` manually."
                )
    else:
        lines.append(
            f"- [ ] GitHub: {github.get('reason', 'not configured')} — "
            "remove the user from the org/repos manually if they had access."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public actions
# ---------------------------------------------------------------------------


async def deprovision_user(
    db: AsyncSession,
    *,
    identifier: str,
    actor: User,
    settings,
    github_username: str | None = None,
    reason: str | None = None,
) -> dict:
    """Full removal: one run revokes access everywhere we can + writes an audit row.

    Returns a JSON-serialisable result: what was revoked per system, the GitHub
    outcome, and the dated manual checklist for the rest.
    """
    user = await resolve_user(db, identifier)
    _guard(user, actor)
    # De-provision demotes + deactivates -> the target does NOT stay an operator.
    await _ensure_not_last_operator(db, user, settings, target_stays_operator=False)
    when = datetime.now(timezone.utc)
    old_role = user.role.value if hasattr(user.role, "value") else str(user.role)

    systems: dict = {}
    # 1) Kill active sessions first (reuse existing revocation).
    systems["sessions_revoked"] = await revoke_all_user_sessions(db, user.id)
    # 2) Deactivate + strip role/features.
    user.is_active = False
    user.role = Role.VIEWER
    user.feature_access_json = None
    systems["account_deactivated"] = True
    systems["role"] = {"from": old_role, "to": Role.VIEWER.value}
    systems["feature_access_cleared"] = True
    # 3) MFA/TOTP + passkeys.
    systems.update(await _revoke_mfa_and_passkeys(db, user))
    # 4) Telephony capability grants.
    systems["telephony"] = await _revoke_telephony_capabilities(db, user, actor)
    await db.commit()

    # 5) GitHub (external, best-effort — after the local commit so a GitHub
    #    outage can never undo the local revocation).
    github = await _remove_from_github(settings, github_username)
    systems["github"] = github

    warnings = _privileged_list_warnings(user.email, settings)
    checklist = build_manual_checklist(
        target_email=user.email, actor_email=actor.email if actor else "system",
        when=when, is_transfer=False, github=github, extra_warnings=warnings,
    )

    # 6) Audit — who de-provisioned whom, when, and which systems were revoked.
    await record_audit(
        db,
        action=AuditAction.USER_DEPROVISIONED,
        result=AuditResult.SUCCESS,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        resource_type="user",
        resource_id=str(user.id),
        metadata={
            "target_email": user.email,
            "reason": reason,
            "systems_revoked": systems,
            "manual_warnings": warnings,
        },
        commit=True,
    )

    return {
        "action": "deprovision",
        "target": {"id": str(user.id), "email": user.email},
        "actor": {"id": str(actor.id) if actor else None, "email": actor.email if actor else None},
        "at": when.isoformat(),
        "systems": systems,
        "warnings": warnings,
        "manual_checklist": checklist,
    }


async def transfer_user(
    db: AsyncSession,
    *,
    identifier: str,
    actor: User,
    settings,
    new_role: Role,
    new_feature_access: dict[str, bool] | None = None,
    reason: str | None = None,
) -> dict:
    """Role change through the SAME audited path: revoke old access, grant new.

    The person stays active (not a departure), but old capability grants are
    cleared (least privilege) and all sessions are revoked so the next login
    picks up the new role/permissions cleanly. Audited as
    ``user_access_transferred``.
    """
    user = await resolve_user(db, identifier)
    _guard(user, actor)
    # A role change only endangers operator coverage if it strips operator status:
    # keeping ADMIN, or being a SUPER_ADMIN_EMAILS entry, means they stay one.
    stays_operator = new_role == Role.ADMIN or (
        (user.email or "").lower() in _super_admin_emails(settings)
    )
    await _ensure_not_last_operator(db, user, settings, target_stays_operator=stays_operator)
    when = datetime.now(timezone.utc)
    old_role = user.role.value if hasattr(user.role, "value") else str(user.role)

    systems: dict = {}
    # Force re-auth so the new role/permissions take effect on next login.
    systems["sessions_revoked"] = await revoke_all_user_sessions(db, user.id)
    # Clear old capability grants — re-granted explicitly for the new role.
    systems["telephony"] = await _revoke_telephony_capabilities(db, user, actor)
    # Apply the new role + (optional) new feature access.
    user.role = new_role
    if new_feature_access is not None:
        user.feature_access_json = json.dumps(new_feature_access)
    systems["role"] = {"from": old_role, "to": new_role.value}
    systems["feature_access"] = "updated" if new_feature_access is not None else "unchanged"
    await db.commit()

    warnings = _privileged_list_warnings(user.email, settings)
    checklist = build_manual_checklist(
        target_email=user.email, actor_email=actor.email if actor else "system",
        when=when, is_transfer=True, github={"attempted": False, "reason": "role change — no GitHub removal"},
        extra_warnings=warnings,
    )

    await record_audit(
        db,
        action=AuditAction.USER_ACCESS_TRANSFERRED,
        result=AuditResult.SUCCESS,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        resource_type="user",
        resource_id=str(user.id),
        metadata={
            "target_email": user.email,
            "reason": reason,
            "role": {"from": old_role, "to": new_role.value},
            "systems_revoked": systems,
            "manual_warnings": warnings,
        },
        commit=True,
    )

    return {
        "action": "transfer",
        "target": {"id": str(user.id), "email": user.email},
        "actor": {"id": str(actor.id) if actor else None, "email": actor.email if actor else None},
        "at": when.isoformat(),
        "systems": systems,
        "warnings": warnings,
        "manual_checklist": checklist,
    }
