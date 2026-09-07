#!/usr/bin/env python
"""Operator command: reset a locked-out user's second factor(s).

Why this exists: a user whose only factor is a passkey has NO recovery path —
recovery codes are minted only during authenticator (TOTP) enrolment, and the
login flow refuses any code for a user without TOTP. Lose the key, lose the
account. Until enrolment mints recovery codes for passkey-only users, this is
the audited way back in — instead of hand SQL on the production database.

Operator-only: --actor must be an ADMIN or an email in SUPER_ADMIN_EMAILS.
Every removal is written to audit_logs (WEBAUTHN_REMOVED / MFA_DISABLED) and
the removed passkey rows are backed up to data/backups/ (chmod 600) first.

Show what would happen:
  .venv/bin/python scripts/mfa_reset.py alice@example.com --actor nathano@ocidm.io --dry-run

Remove passkeys only (keeps an authenticator app if one is enrolled):
  .venv/bin/python scripts/mfa_reset.py alice@example.com --actor nathano@ocidm.io --passkeys --reason "USB key lost"

Remove everything (passkeys + TOTP + recovery codes) -> password-only login:
  .venv/bin/python scripts/mfa_reset.py alice@example.com --actor nathano@ocidm.io --all --reason "phone + key lost"

The user should re-enrol a factor from Settings -> Security as soon as they are in.
"""
import argparse
import asyncio
import json
import os
import sys
import time

from sqlalchemy import select

from app.audit.service import AuditAction, AuditResult, safe_record_audit
from app.auth.models import Role, User
from app.auth.webauthn_models import WebAuthnCredential
from app.config import Settings
from app.database import build_engine, build_session_factory


async def _load_actor(db, email: str, settings: Settings) -> User | None:
    actor = (await db.execute(select(User).where(User.email.ilike(email.strip())))).scalar_one_or_none()
    super_emails = {e.strip().lower() for e in (settings.super_admin_emails or "").split(",") if e.strip()}
    is_super = email.strip().lower() in super_emails
    if actor is None and not is_super:
        raise SystemExit(f"Actor {email!r} not found and not in SUPER_ADMIN_EMAILS. Refusing.")
    if actor is not None and not (actor.role == Role.ADMIN or actor.email.lower() in super_emails):
        raise SystemExit(f"Actor {email!r} is not an operator (role={actor.role.value}). Refusing.")
    return actor


def _row_dict(cred: WebAuthnCredential) -> dict:
    return {c.name: getattr(cred, c.name) for c in cred.__table__.columns}


async def _run(args) -> dict:
    settings = Settings()
    engine = build_engine(settings.database_url)
    Session = build_session_factory(engine)
    summary: dict = {"user": args.email, "dry_run": args.dry_run, "passkeys_removed": 0, "totp_removed": False, "backup": None}
    try:
        async with Session() as db:
            actor = await _load_actor(db, args.actor, settings)
            user = (await db.execute(select(User).where(User.email.ilike(args.email.strip())))).scalar_one_or_none()
            if user is None:
                raise SystemExit(f"User {args.email!r} not found.")

            creds = list((await db.execute(
                select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
            )).scalars())
            summary["passkeys_found"] = [
                {"id": str(c.id), "name": getattr(c, "device_name", None) or getattr(c, "name", None), "created_at": str(getattr(c, "created_at", ""))}
                for c in creds
            ]
            summary["totp_enabled"] = bool(user.mfa_enabled)
            summary["recovery_codes"] = bool(user.mfa_recovery_codes)

            do_passkeys = args.passkeys or args.all
            do_totp = args.totp or args.all
            if not (do_passkeys or do_totp) and not args.dry_run:
                raise SystemExit("Nothing selected: pass --passkeys, --totp, --all, or --dry-run.")
            if args.dry_run:
                summary["would_remove"] = {"passkeys": len(creds) if (do_passkeys or not do_totp) else 0,
                                          "totp": bool(user.mfa_enabled) if (do_totp or not do_passkeys) else False}
                return summary

            if do_passkeys and creds:
                os.makedirs("data/backups", exist_ok=True)
                path = f"data/backups/passkey_{user.email.split('@')[0]}_{int(time.time())}.json"
                with open(path, "w") as fh:
                    json.dump([_row_dict(c) for c in creds], fh, default=str)
                os.chmod(path, 0o600)
                summary["backup"] = path
                for c in creds:
                    await db.delete(c)
                    await safe_record_audit(
                        db, action=AuditAction.WEBAUTHN_REMOVED, result=AuditResult.SUCCESS,
                        actor_id=actor.id if actor else None, actor_email=args.actor,
                        metadata={"target": user.email, "credential_id": str(c.id), "reason": args.reason, "via": "scripts/mfa_reset.py"},
                    )
                summary["passkeys_removed"] = len(creds)

            if do_totp and (user.mfa_enabled or user.mfa_secret or user.mfa_recovery_codes):
                user.mfa_enabled = False
                user.mfa_secret = None
                user.mfa_recovery_codes = None
                if hasattr(user, "mfa_enrolled_at"):
                    user.mfa_enrolled_at = None
                await safe_record_audit(
                    db, action=AuditAction.MFA_DISABLED, result=AuditResult.SUCCESS,
                    actor_id=actor.id if actor else None, actor_email=args.actor,
                    metadata={"target": user.email, "reason": args.reason, "via": "scripts/mfa_reset.py"},
                )
                summary["totp_removed"] = True

            await db.commit()
            remaining = (await db.execute(
                select(WebAuthnCredential.id).where(WebAuthnCredential.user_id == user.id)
            )).scalars().all()
            summary["login_now"] = "password-only" if (not remaining and not user.mfa_enabled) else "still MFA-gated"
            return summary
    finally:
        await engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("email", help="the locked-out user")
    p.add_argument("--actor", required=True, help="operator email performing the reset (audited)")
    p.add_argument("--passkeys", action="store_true", help="remove all registered passkeys")
    p.add_argument("--totp", action="store_true", help="remove the authenticator app + recovery codes")
    p.add_argument("--all", action="store_true", help="remove every second factor -> password-only")
    p.add_argument("--reason", default="", help="free text, written to the audit log")
    p.add_argument("--dry-run", action="store_true", help="report only, change nothing")
    args = p.parse_args()
    if not args.dry_run and not args.reason:
        p.error("--reason is required unless --dry-run")
    print(json.dumps(asyncio.run(_run(args)), indent=2, default=str))


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
