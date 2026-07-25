"""In-place at-rest encryption/decryption of existing Plaid financial data.

Operates at the RAW SQL level, deliberately bypassing the ORM's transparent
``EncryptedString``/``EncryptedNumeric`` columns — otherwise it would
double-encrypt on write or fail decrypting plaintext on read. Idempotent: any
value that already decrypts under the Fernet key is left untouched, so both the
Alembic migration and the standalone script are safe to re-run.

Fail-closed: ``load_fernet_or_fail`` refuses to run without FERNET_KEY, so the
migration can never "encrypt" data to plaintext. This mirrors the app boot guard
and reuses the SAME key (no second key system).
"""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

#: Plaid consumer-financial fields that are encrypted at rest. Keep in lockstep
#: with the EncryptedString/EncryptedNumeric columns in models.py.
ENCRYPTED_FIELDS: dict[str, list[str]] = {
    "plaid_transactions": ["account_id", "amount", "name", "merchant_name", "category"],
    "plaid_connections": ["institution_name", "accounts_json"],
}


def load_fernet_or_fail() -> Fernet:
    """Build a Fernet from the app's FERNET_KEY, or raise. Fail CLOSED — never
    migrate financial data while the key is missing.

    Reads the key via ``Settings`` (which loads backend/.env, exactly like the
    app) with an os.environ fallback — because ``alembic upgrade head`` in
    deploy.sh does NOT export .env into the environment (only the systemd unit
    does), so a raw ``os.getenv`` would spuriously fail closed on deploy.
    """
    from app.config import Settings

    key = Settings().fernet_key or os.getenv("FERNET_KEY", "")
    if not key:
        raise RuntimeError(
            "FERNET_KEY is not set — refusing to run the Plaid at-rest encryption "
            "migration. Set FERNET_KEY (the same key the app uses) and re-run."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def _is_encrypted(fernet: Fernet, value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        fernet.decrypt(value.encode())
        return True
    except (InvalidToken, ValueError):
        return False


def encrypt_existing(conn, fernet: Fernet, *, dry_run: bool) -> dict:
    """Encrypt every configured plaintext field in place.

    ``conn`` is a SYNC SQLAlchemy Connection (e.g. ``op.get_bind()`` in a
    migration, or ``engine.begin()`` in the CLI). Returns a per-table summary
    with before/after counts.
    """
    from sqlalchemy import text

    summary: dict = {}
    for table, fields in ENCRYPTED_FIELDS.items():
        col_list = ", ".join(["id", *fields])
        rows = conn.execute(text(f"SELECT {col_list} FROM {table}")).mappings().all()
        newly_encrypted = 0
        already = 0
        for row in rows:
            updates = {}
            for field in fields:
                val = row[field]
                if val is None or _is_encrypted(fernet, val):
                    continue
                updates[field] = fernet.encrypt(str(val).encode()).decode()
            if updates:
                newly_encrypted += 1
                if not dry_run:
                    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
                    conn.execute(
                        text(f"UPDATE {table} SET {set_clause} WHERE id = :row_id"),
                        {**updates, "row_id": row["id"]},
                    )
            else:
                already += 1
        summary[table] = {
            "rows_total": len(rows),
            "rows_encrypted": newly_encrypted,
            "rows_already_done": already,
        }
    return summary


def decrypt_existing(conn, fernet: Fernet) -> dict:
    """Reverse of ``encrypt_existing`` — write plaintext back. Used by the
    migration downgrade / rollback. Idempotent."""
    from sqlalchemy import text

    summary: dict = {}
    for table, fields in ENCRYPTED_FIELDS.items():
        col_list = ", ".join(["id", *fields])
        rows = conn.execute(text(f"SELECT {col_list} FROM {table}")).mappings().all()
        reverted = 0
        for row in rows:
            updates = {}
            for field in fields:
                val = row[field]
                if val is None or not _is_encrypted(fernet, val):
                    continue
                updates[field] = fernet.decrypt(val.encode()).decode()
            if updates:
                reverted += 1
                set_clause = ", ".join(f"{k} = :{k}" for k in updates)
                conn.execute(
                    text(f"UPDATE {table} SET {set_clause} WHERE id = :row_id"),
                    {**updates, "row_id": row["id"]},
                )
        summary[table] = {"rows_total": len(rows), "rows_decrypted": reverted}
    return summary
