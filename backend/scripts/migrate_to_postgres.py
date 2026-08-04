"""Type-safe SQLite -> Postgres data migration for the Accountant DB.

Moving live financial data from SQLite (loosely typed) to Postgres (strictly
typed) is delicate: UUIDs are stored as CHAR(32) in SQLite but are native `uuid`
in Postgres, booleans are 0/1 integers, and several columns are encrypted at
rest. This migrator avoids all of that by going through the ORM's own column
types, which know how to decode from SQLite and encode for Postgres:

  1. Build the FULL current schema on the target with Base.metadata.create_all
     (correct per-dialect types — not a lossy reflection of the SQLite file).
  2. Copy every table in FK-dependency order (Base.metadata.sorted_tables),
     reading with the SQLite result-processors and writing with the Postgres
     bind-processors, so UUIDs / booleans / JSON / datetimes / encrypted columns
     all convert correctly. (Encrypted values are decrypted on read and
     re-encrypted on write with the SAME FERNET_KEY, so they stay encrypted.)
  3. Reset integer sequences on Postgres (UUID PKs need none, but any serial
     column would otherwise collide on the next insert).
  4. Print per-table row counts so you can verify against the source.

Usage (run ON a machine that has FERNET_KEY set, e.g. the VPS):

    SOURCE_URL="sqlite+aiosqlite:///./data/accountant.db" \
    DEST_URL="postgresql+asyncpg://user:pass@host:5432/dbname" \
    .venv/bin/python scripts/migrate_to_postgres.py

DEST_URL is required. The script REFUSES to run without an explicit target, and
never writes to the source. It does NOT drop/flip anything — you point the app at
Postgres yourself once counts verify. See POSTGRES_MIGRATION.md.
"""
import asyncio
import os
import sys

# --- Register every model so Base.metadata is the COMPLETE schema. Mirrors
#     tests.conftest._import_all_models / app.main's import block. -------------
import app.auth.models  # noqa: F401
import app.auth.webauthn_models  # noqa: F401
import app.audit.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.collaboration.models  # noqa: F401
import app.notifications.models  # noqa: F401
import app.calendar.models  # noqa: F401
import app.accounting.models  # noqa: F401
import app.contacts.models  # noqa: F401
import app.invoicing.models  # noqa: F401
import app.income.models  # noqa: F401
import app.recurring.models  # noqa: F401
import app.budgets.models  # noqa: F401
import app.email.models  # noqa: F401
import app.integrations.gmail.models  # noqa: F401
import app.integrations.plaid.models  # noqa: F401
import app.integrations.plaid.categorization_models  # noqa: F401
import app.integrations.stripe.models  # noqa: F401
import app.integrations.stripe_connect.models  # noqa: F401
import app.cards.models  # noqa: F401
import app.widget.models  # noqa: F401
import app.billing.models  # noqa: F401
import app.integrations.twilio.models  # noqa: F401
import app.estimates.models  # noqa: F401
import app.invoicing.reminder_models  # noqa: F401
import app.invoicing.credit_models  # noqa: F401
import app.integrations.settings_models  # noqa: F401
import app.accounting.period_models  # noqa: F401
import app.accounting.tax_models  # noqa: F401
import app.accounting.ledger_models  # noqa: F401
import app.operators.models  # noqa: F401
import app.cashbook.models  # noqa: F401
import app.personal.models  # noqa: F401
import app.meetings.models  # noqa: F401
import app.office.models  # noqa: F401
import app.settings.models  # noqa: F401
import app.public.models  # noqa: F401
import app.proposals.models  # noqa: F401
import app.reconciliation.models  # noqa: F401
import app.inbox.models  # noqa: F401
import app.core.idempotency  # noqa: F401
import app.forms.models  # noqa: F401
import app.communication.models  # noqa: F401
import app.workflows.models  # noqa: F401
import app.pages.models  # noqa: F401
import app.scheduling.models  # noqa: F401
import app.branding.models  # noqa: F401
import app.brain.models  # noqa: F401
import app.platform_admin.models  # noqa: F401
import app.events.models  # noqa: F401

from sqlalchemy import Integer, inspect, insert, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core.encryption import init_encryption_service  # noqa: E402
from app.database import Base  # noqa: E402

def _normalize_dest(url: str) -> str:
    """Accept a Postgres URL exactly as Supabase (or any host) hands it over and
    make it work with our async driver — so the person running the migration
    doesn't have to hand-edit the format (the easiest thing to get wrong):

      - `postgres://...` / `postgresql://...`  ->  `postgresql+asyncpg://...`
      - ensure `prepared_statement_cache_size=0` (required for asyncpg through
        Supabase's connection pooler; harmless on a direct connection).

    A sqlite URL passes through untouched.
    """
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+asyncpg://") and "prepared_statement_cache_size" not in url:
        url += ("&" if "?" in url else "?") + "prepared_statement_cache_size=0"
    return url


SOURCE_URL = os.environ.get("SOURCE_URL", "sqlite+aiosqlite:///./data/accountant.db")
DEST_URL = os.environ.get("DEST_URL") or os.environ.get("TARGET_URL")
if DEST_URL:
    DEST_URL = _normalize_dest(DEST_URL)
BATCH = 500


def _fatal(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


async def _reset_sequences(dest_engine, tables) -> None:
    """Point each integer PK's sequence past the max id we just inserted so the
    next insert doesn't collide. No-op for UUID PKs and non-Postgres targets."""
    if dest_engine.dialect.name != "postgresql":
        return
    async with dest_engine.begin() as conn:
        for table in tables:
            for col in table.primary_key.columns:
                if isinstance(col.type, Integer):
                    await conn.execute(text(
                        "SELECT setval(pg_get_serial_sequence(:t, :c), "
                        "COALESCE((SELECT MAX(%s) FROM %s), 1))" % (col.name, table.name)
                    ), {"t": table.name, "c": col.name})


async def main() -> None:
    if not DEST_URL:
        _fatal("DEST_URL is required (a postgresql+asyncpg://... URL). Refusing to run without a target.")
    if DEST_URL.startswith("sqlite") and DEST_URL == SOURCE_URL:
        _fatal("DEST_URL must differ from SOURCE_URL.")

    settings = Settings()
    if settings.fernet_key:
        init_encryption_service(settings.fernet_key)  # needed to round-trip encrypted columns
    else:
        print("WARNING: FERNET_KEY not set — encrypted columns will fail. Run where the key is configured.")

    src = create_async_engine(SOURCE_URL)
    dst = create_async_engine(DEST_URL)

    print(f"source: {SOURCE_URL}")
    print(f"target: {DEST_URL.split('@')[-1] if '@' in DEST_URL else DEST_URL}")

    # 1. Build the full current schema on the target from the models.
    print("\n== building schema on target ==")
    async with dst.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Copy every table in FK-dependency order.
    print("\n== copying data ==")
    tables = list(Base.metadata.sorted_tables)
    total = 0
    async with src.connect() as sconn:
        src_tables = set(await sconn.run_sync(lambda c: inspect(c).get_table_names()))
        for table in tables:
            if table.name not in src_tables:
                # A model table the source never created (an unused feature).
                print(f"  {table.name:38} (absent in source — skipped)")
                continue
            rows = (await sconn.execute(select(table))).mappings().all()
            if not rows:
                print(f"  {table.name:38} 0")
                continue
            async with dst.begin() as dconn:
                for i in range(0, len(rows), BATCH):
                    await dconn.execute(insert(table), [dict(r) for r in rows[i:i + BATCH]])
            total += len(rows)
            print(f"  {table.name:38} {len(rows)}")

    # 3. Fix integer sequences on Postgres.
    await _reset_sequences(dst, tables)

    print(f"\nDONE. Copied {total} rows across {len(tables)} tables.")
    print("Next: verify row counts + spot-check financial totals, then point")
    print("DATABASE_URL at Postgres and restart. Keep the SQLite backup.")

    await src.dispose()
    await dst.dispose()


if __name__ == "__main__":
    asyncio.run(main())
