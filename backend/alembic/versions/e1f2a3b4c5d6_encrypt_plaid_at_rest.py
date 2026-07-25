"""encrypt Plaid consumer-financial data at rest

Encrypts existing rows in plaid_transactions + plaid_connections in place using
the app's Fernet key. Idempotent (already-encrypted values are skipped) and
fail-closed (raises if FERNET_KEY is unset). Runs during `alembic upgrade head`
in deploy.sh — which now backs up the DB first — so the backlog is encrypted
BEFORE the new app (with the EncryptedString columns) restarts.

Revision ID: e1f2a3b4c5d6
Revises: d6e7f8a9b0c1
Create Date: 2026-07-25
"""
from alembic import op

from app.integrations.plaid.at_rest import (
    decrypt_existing,
    encrypt_existing,
    load_fernet_or_fail,
)

revision = "e1f2a3b4c5d6"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    fernet = load_fernet_or_fail()  # fail closed if FERNET_KEY unset
    summary = encrypt_existing(op.get_bind(), fernet, dry_run=False)
    print(f"[at-rest] Plaid encryption applied: {summary}")


def downgrade() -> None:
    # Rollback: decrypt back to plaintext so the previous app version reads it.
    fernet = load_fernet_or_fail()
    summary = decrypt_existing(op.get_bind(), fernet)
    print(f"[at-rest] Plaid encryption reverted (downgrade): {summary}")
