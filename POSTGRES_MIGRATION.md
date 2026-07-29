# Migrating the Accountant DB: SQLite → PostgreSQL

**Why:** production runs on a single SQLite file. That's the biggest reliability
risk for a financial app — no concurrent-write scaling, no managed backups, no
replication. Moving to a managed Postgres (Supabase) fixes all three. This is the
"reliability" step of the roadmap.

**Who runs this:** you. It provisions infrastructure and moves live financial
data — the assistant prepared and validated the tooling, but you provision the
database, hold the credentials, and flip the switch.

The tooling: [`backend/scripts/migrate_to_postgres.py`](backend/scripts/migrate_to_postgres.py)
— it builds the **full current schema** on Postgres from the ORM models (correct
native types), then copies every table in FK-dependency order through the ORM's
own type processors, so UUIDs, booleans, JSON, datetimes and **encrypted columns**
all convert correctly. Validated SQLite→SQLite on the real dataset (row counts
matched); the only Postgres-specific paths (native `uuid`, sequence reset) run
only against a real Postgres.

---

## 0. Prerequisites
- A managed Postgres. **Supabase** fits the stack. Create a project, then copy
  its connection string. Use the **session/direct** connection string for the
  migration (not the transaction pooler), converted to the async driver:
  `postgresql+asyncpg://postgres:<pw>@<host>:5432/postgres`
- Install the async driver on the box: `.venv/bin/pip install asyncpg`
- **FERNET_KEY must be identical** on the Postgres-backed app. Encrypted columns
  are decrypted on read and re-encrypted on write with this key — do NOT
  regenerate it, or existing encrypted data becomes unreadable.

## 1. Freeze + back up
```bash
cd ~/Accountant
bash scripts/backup.sh                 # snapshot the SQLite file first
bash stop.sh                           # stop the backend so nothing writes mid-copy
```

## 2. Run the migration
```bash
cd ~/Accountant/backend
DEST_URL="postgresql+asyncpg://postgres:<pw>@<host>:5432/postgres" \
  .venv/bin/python scripts/migrate_to_postgres.py
```
It prints a per-table row count and a total. The source SQLite is only read from,
never written.

## 3. Verify BEFORE flipping
- **Row counts** match the source. Spot check the ones that matter:
  ```bash
  # source counts
  .venv/bin/python -c "import sqlite3;c=sqlite3.connect('data/accountant.db');[print(t, c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]) for t in ('users','cashbook_entries','payment_accounts','chart_accounts','plaid_transactions','plaid_connections')]"
  ```
  Then the same counts against Postgres (psql or the Supabase table view).
- **Financials tie out** on Postgres before trusting it: the Balance Sheet still
  balances and the P&L totals are unchanged (open Financial Statements once the
  app points at Postgres in step 5, or query the reports).

## 4. Stamp Alembic
The schema came from `create_all`, so tell Alembic it's current (future
migrations then apply cleanly):
```bash
DATABASE_URL="postgresql+asyncpg://..." .venv/bin/python -m alembic stamp head
```

## 5. Cut over
- In `backend/.env`, set `DATABASE_URL=postgresql+asyncpg://postgres:<pw>@<host>:5432/postgres`
  (keep everything else — **FERNET_KEY unchanged**).
- `bash start.sh` and health-check: `curl -s http://127.0.0.1:8000/api/system/health`
- Log in and confirm the Cashbook, Financial Statements, and Bank Scanner show
  the same data.

## 6. Rollback (if anything looks off)
The SQLite file is untouched. Revert `DATABASE_URL` in `backend/.env` back to
`sqlite+aiosqlite:///./data/accountant.db`, `bash stop.sh && bash start.sh`, and
you're exactly where you started. Keep the SQLite backup for at least a couple of
weeks after cutover.

## Notes / gotchas
- **Pooler vs direct:** run the *migration* against the direct/session string.
  For the *running app*, Supabase's transaction pooler is fine; if you use it,
  disable server-side prepared statements for asyncpg (`?prepared_statement_cache_size=0`).
- **`schema_patch` becomes a no-op** on Postgres (it's SQLite-only) — the schema
  is complete from `create_all` + Alembic. Migrations are already Postgres-first.
- **Re-runs:** the copy assumes an empty target. To retry, drop/recreate the
  Postgres database (or its `public` schema) first so `create_all` starts clean.
