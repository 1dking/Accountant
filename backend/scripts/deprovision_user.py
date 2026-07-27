#!/usr/bin/env python
"""Operator command: revoke a departing/transferred user's access in one run.

Runs the same audited path as the platform-admin endpoints
(app/platform_admin/deprovision.py). Operator-only: the --actor must resolve to
an ADMIN or an email in SUPER_ADMIN_EMAILS, or the command refuses.

Departure (full removal):
  .venv/bin/python scripts/deprovision_user.py alice@example.com \
      --actor nathano@ocidm.io --github-username alice-gh --reason "left the team"

Transfer (role change):
  .venv/bin/python scripts/deprovision_user.py alice@example.com \
      --actor nathano@ocidm.io --transfer --new-role manager --reason "promoted"

It prints a JSON summary of what was revoked and the dated MANUAL CHECKLIST for
the steps that can't be automated (SSH keys, console seats, .env allow-lists).
"""
import argparse
import asyncio
import json
import sys

from app.auth.models import Role, User
from app.config import Settings
from app.database import build_engine, build_session_factory
from app.platform_admin.deprovision import deprovision_user, resolve_user, transfer_user
from sqlalchemy import select


async def _load_actor(db, email: str, settings: Settings) -> User:
    actor = (
        await db.execute(select(User).where(User.email.ilike(email.strip())))
    ).scalar_one_or_none()
    super_emails = {
        e.strip().lower() for e in (settings.super_admin_emails or "").split(",") if e.strip()
    }
    is_super = email.strip().lower() in super_emails
    if actor is None and not is_super:
        raise SystemExit(f"Actor {email!r} not found and not in SUPER_ADMIN_EMAILS. Refusing.")
    if actor is not None:
        is_admin = actor.role == Role.ADMIN
        if not (is_admin or actor.email.lower() in super_emails):
            raise SystemExit(
                f"Actor {email!r} is not an operator (role={actor.role.value}, "
                "not in SUPER_ADMIN_EMAILS). Refusing."
            )
    return actor


async def _run(args) -> dict:
    settings = Settings()
    engine = build_engine(settings.database_url)
    Session = build_session_factory(engine)
    try:
        async with Session() as db:
            actor = await _load_actor(db, args.actor, settings)
            # Confirm the target exists before doing anything (clearer error).
            await resolve_user(db, args.identifier)
            if args.transfer:
                if not args.new_role:
                    raise SystemExit("--transfer requires --new-role")
                feats = json.loads(args.feature_access) if args.feature_access else None
                return await transfer_user(
                    db, identifier=args.identifier, actor=actor, settings=settings,
                    new_role=Role(args.new_role), new_feature_access=feats, reason=args.reason,
                )
            return await deprovision_user(
                db, identifier=args.identifier, actor=actor, settings=settings,
                github_username=args.github_username, reason=args.reason,
            )
    finally:
        await engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description="Revoke a user's access across systems (audited).")
    p.add_argument("identifier", help="Target user's email or id (UUID).")
    p.add_argument("--actor", required=True, help="Operator running this (email). Must be ADMIN / super-admin.")
    p.add_argument("--github-username", help="GitHub handle to remove as a repo collaborator.")
    p.add_argument("--reason", help="Free-text reason, recorded in the audit row.")
    p.add_argument("--transfer", action="store_true", help="Role change instead of full removal.")
    p.add_argument("--new-role", choices=[r.value for r in Role], help="New role for --transfer.")
    p.add_argument("--feature-access", help="JSON object of feature->bool for --transfer (optional).")
    args = p.parse_args()

    result = asyncio.run(_run(args))

    summary = {k: v for k, v in result.items() if k != "manual_checklist"}
    print(json.dumps(summary, indent=2, default=str))
    print("\n" + "=" * 70 + "\n")
    print(result["manual_checklist"])
    sys.stdout.flush()


if __name__ == "__main__":
    main()
