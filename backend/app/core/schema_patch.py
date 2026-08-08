"""Idempotent additive schema patches for the SQLite production DB.

``Base.metadata.create_all`` creates MISSING tables but never alters EXISTING
ones — so new columns added to a long-lived table (``users``) never appear on the
production SQLite DB, and every query for them would error. This runs on startup
(SQLite only) and ``ALTER TABLE ... ADD COLUMN`` for any missing column.

Additive and idempotent by construction: it only ever adds columns that aren't
already present, so it's safe to run on every boot. New TABLES continue to come
from create_all; this covers only new COLUMNS on pre-existing tables. For a
Postgres deployment, use a real Alembic migration instead (see PREREQUISITES_REPORT.md).
"""

import logging

logger = logging.getLogger(__name__)

#: table -> {column_name: column DDL}. All additive; NOT NULL columns must carry
#: a DEFAULT so the ALTER succeeds against existing rows.
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "mfa_enabled": "BOOLEAN NOT NULL DEFAULT 0",
        "mfa_secret": "VARCHAR(512)",
        "mfa_recovery_codes": "TEXT",
        "mfa_enrolled_at": "DATETIME",
        "anonymized_at": "DATETIME",
        # Business/Personal ledger toggle. Defaults 'business' so every existing
        # user keeps today's behaviour until they opt into Personal mode.
        "active_mode": "VARCHAR(20) NOT NULL DEFAULT 'business'",
    },
    # Bank Scanner: link a payment account to its Plaid account, and a synced
    # bank transaction to the Cashbook entry it was posted to. Both nullable and
    # additive — existing rows are simply NULL. (UUID FKs are stored CHAR(32) in
    # this SQLite build, matching the columns above; the index on
    # plaid_account_id comes from create_all on a fresh DB / the alembic
    # migration on Postgres — it isn't recreated here, which is fine at this
    # data scale.)
    "payment_accounts": {
        "plaid_account_id": "VARCHAR(255)",
    },
    "plaid_transactions": {
        "matched_cashbook_entry_id": "CHAR(32)",
        # Back-link when a personal-tagged bank txn is copied to the Personal ledger.
        "matched_personal_transaction_id": "CHAR(32)",
    },
    # Ties an auto-provisioned personal mirror account to its source bank account.
    "personal_accounts": {
        "external_key": "VARCHAR(255)",
    },
    # Org-wide bank visibility: a Plaid connection can belong to an org so peers
    # with org cashbook access see it. Nullable/additive; backfilled per the
    # shared-workspace setup. (Managing the connection stays owner-only in code.)
    "plaid_connections": {
        "org_id": "CHAR(32)",
    },
    # Least-privilege telephony capability grants. Every one defaults to 0 —
    # an existing subaccount is DENIED until an operator grants a capability.
    "telephony_accounts": {
        "allow_voice_outbound": "BOOLEAN NOT NULL DEFAULT 0",
        "allow_voice_inbound": "BOOLEAN NOT NULL DEFAULT 0",
        "allow_sms": "BOOLEAN NOT NULL DEFAULT 0",
        "allow_mms": "BOOLEAN NOT NULL DEFAULT 0",
        "allow_number_purchase": "BOOLEAN NOT NULL DEFAULT 0",
        "allow_markup": "BOOLEAN NOT NULL DEFAULT 0",
        "capabilities_updated_by": "CHAR(32)",
        "capabilities_updated_at": "DATETIME",
    },
    # WAIT_DELAY resumption: a linear execution that hits a delay parks in
    # WAITING and the resume poller continues it once resume_at is past. All
    # nullable/additive — existing rows are simply NULL and untouched.
    "workflow_executions": {
        "resume_at": "DATETIME",
        "resume_step_index": "INTEGER",
        "context_json": "TEXT",
    },
}


async def apply_sqlite_column_patches(engine) -> None:
    async with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            existing = await _existing_columns(conn, table)
            if not existing:
                # Table absent (fresh DB) — create_all will build it in full.
                continue
            for col, ddl in columns.items():
                if col not in existing:
                    await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
                    logger.info("schema_patch: added column %s.%s", table, col)


async def _existing_columns(conn, table: str) -> set[str]:
    result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return {row[1] for row in result}  # row[1] = column name
