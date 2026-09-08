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
        # S5: team block reads these; nothing else does.
        "public_title": "VARCHAR(120)",
        "public_bio": "TEXT",
        "avatar_url": "VARCHAR(500)",
        "show_on_site": "BOOLEAN NOT NULL DEFAULT 1",
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
    # Page builder site catalogue (alembic m1j2k3l4m5n6). Additive on
    # company_settings + users; new tables (catalog_items, page_reviews,
    # page_faqs) come from create_all on a fresh SQLite DB.
    "company_settings": {
        "org_id": "CHAR(32)",
        "tagline": "VARCHAR(255)",
        "business_hours_json": "TEXT",
        "google_place_id": "VARCHAR(255)",
        "service_area_text": "VARCHAR(500)",
        "map_embed_url": "VARCHAR(1000)",
        "brand_primary_color": "VARCHAR(9)",
        "booking_calendar_slug": "VARCHAR(255)",
        "lead_form_id": "CHAR(32)",
    },
    # Page builder block model v2 (alembic l0i1b2c3d4e5 on Postgres). All
    # nullable/defaulted — the 18 v1 seeds keep working with NULLs.
    "section_variants": {
        "fields_schema": "JSON",
        "data_source": "VARCHAR(32)",
        "data_mode": "VARCHAR(16)",
        "behaviour": "VARCHAR(64)",
        "capabilities": "JSON",
        "motion_preset": "VARCHAR(64)",
        "locale_props": "JSON",
        "thumbnail_hash": "VARCHAR(64)",
        "thumbnail_rendered_at": "DATETIME",
        "schema_version": "INTEGER NOT NULL DEFAULT 1",
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
    # ── Canadian tax matrix (alembic i7f8a9b0c1d2). All nullable/defaulted. ──
    # NOTE: this key is merged into the S5 company_settings block above at
    # import time (see `_MERGE_INTO_COMPANY_SETTINGS` below). Python's dict
    # semantics silently overwrite a repeated key, so keeping the two
    # blocks separate would drop one set. Both sets stay listed for clarity.
    "_company_settings_tax_identity": {
        "province": "VARCHAR(2)",
        "business_number": "VARCHAR(15)",
        "gst_hst_number": "VARCHAR(15)",
        "fiscal_year_end_month": "INTEGER",
    },
    "tax_rates": {
        "tax_type": "VARCHAR(10)",
        "province": "VARCHAR(2)",
        "is_recoverable": "BOOLEAN NOT NULL DEFAULT 1",
        "is_system": "BOOLEAN NOT NULL DEFAULT 0",
        "effective_from": "DATE",
    },
    # Split tax components. tax_amount stays the total; these are the CRA vs.
    # province halves. tax_rates.id is VARCHAR(36) in this schema.
    "cashbook_entries": {
        "tax_gst_hst_amount": "NUMERIC(12, 2)",
        "tax_pst_amount": "NUMERIC(12, 2)",
        "tax_rate_id": "VARCHAR(36)",
        "tax_rate_2_id": "VARCHAR(36)",
    },
    "invoices": {
        "tax_gst_hst_amount": "NUMERIC(12, 2)",
        "tax_pst_amount": "NUMERIC(12, 2)",
        "tax_rate_id": "VARCHAR(36)",
        "tax_rate_2_id": "VARCHAR(36)",
    },
    "invoice_line_items": {
        "tax_rate_2": "NUMERIC(5, 2)",
        "tax_rate_id": "VARCHAR(36)",
        "tax_rate_2_id": "VARCHAR(36)",
    },
    "expenses": {
        "tax_gst_hst_amount": "NUMERIC(12, 2)",
        "tax_pst_amount": "NUMERIC(12, 2)",
        "tax_rate_id": "VARCHAR(36)",
        "tax_rate_2_id": "VARCHAR(36)",
    },
    # Joint filing (alembic k9h0a1b2c3d4): which T1 line a personal category feeds.
    "personal_categories": {
        "t1_line": "VARCHAR(10)",
    },
}


# Fold the "_company_settings_tax_identity" alias into the real
# company_settings block (see the note next to that key). Keeps the
# two logical groupings while ensuring both sets of ALTERs actually run.
_ADDITIVE_COLUMNS["company_settings"].update(
    _ADDITIVE_COLUMNS.pop("_company_settings_tax_identity", {})
)

# Wave-2 domains (S8): email_enabled on already-created domain_purchases
_ADDITIVE_COLUMNS["domain_purchases"] = {
    "email_enabled": "BOOLEAN DEFAULT 0 NOT NULL",
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
