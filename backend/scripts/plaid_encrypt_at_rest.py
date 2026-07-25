#!/usr/bin/env python
"""Encrypt existing Plaid consumer-financial data at rest (dry-run by default).

Idempotent + fail-closed. The Alembic migration (e1f2a3b4c5d6) does the same
thing automatically on deploy; this is the operator tool for previewing and
verifying, and for a manual backfill.

Usage (from backend/, with the venv):
  .venv/bin/python scripts/plaid_encrypt_at_rest.py            # DRY-RUN, prints counts
  .venv/bin/python scripts/plaid_encrypt_at_rest.py --apply    # backs up, then encrypts
  .venv/bin/python scripts/plaid_encrypt_at_rest.py --decrypt --apply   # rollback

Requires FERNET_KEY in the environment (same key the app uses). Refuses to run
without it.
"""
import argparse
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from app.config import Settings  # noqa: E402
from app.integrations.plaid.at_rest import (  # noqa: E402
    decrypt_existing,
    encrypt_existing,
    load_fernet_or_fail,
)


def _sync_url(async_url: str) -> str:
    return async_url.replace("+aiosqlite", "").replace("+asyncpg", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument("--decrypt", action="store_true", help="Reverse: decrypt back to plaintext")
    args = parser.parse_args()
    dry_run = not args.apply

    if args.decrypt and dry_run:
        parser.error("--decrypt requires --apply (rollback always writes).")

    fernet = load_fernet_or_fail()  # fail closed on missing FERNET_KEY

    if args.apply:
        repo_root = Path(__file__).resolve().parents[2]
        backup = repo_root / "scripts" / "backup.sh"
        if backup.is_file():
            print(">>> Backing up database before mutation …")
            subprocess.run(["bash", str(backup)], check=True)
        else:
            print(f"WARNING: {backup} not found — proceeding without a backup.")

    url = _sync_url(Settings().database_url)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            if args.decrypt:
                summary = decrypt_existing(conn, fernet)
            else:
                summary = encrypt_existing(conn, fernet, dry_run=dry_run)
    finally:
        engine.dispose()

    mode = "DRY-RUN (no changes written)" if dry_run else ("DECRYPTED" if args.decrypt else "ENCRYPTED")
    print(f"\n=== {mode} ===")
    for table, counts in summary.items():
        print(f"  {table}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
