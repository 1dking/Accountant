# Encryption at Rest — Plaid Consumer Financial Data

Application-layer encryption for consumer financial data retrieved from Plaid, using the **same
Fernet key** already protecting credentials/tokens ([app/core/encryption.py](backend/app/core/encryption.py)).
No second key system; the existing `FERNET_KEY` boot guard is unchanged and unweakened.

## How it works

Transparent SQLAlchemy column types in [app/core/encrypted_types.py](backend/app/core/encrypted_types.py):
- `EncryptedString` — encrypt-on-write, decrypt-on-read for text.
- `EncryptedNumeric` — same, stored as the ciphertext of the decimal string; returns `Decimal`.

Application code and queries are unchanged — the encrypt/decrypt happens in the column type, so
services, routers, categorization, and AI categorization read/write plaintext as before.

**Fail-closed:** both types call `get_encryption_service()`, which raises if the service isn't
initialized (which only happens when the boot guard has already refused to start on a missing
`FERNET_KEY`). That error is deliberately not caught — a missing key can never cause a silent
plaintext write/read. **Read tolerance:** a value that isn't a Fernet token (legacy plaintext, e.g.
mid-migration) is returned as-is and logged, so a partially-migrated table never crashes reads.

## What IS encrypted

**`plaid_transactions`** ([models.py](backend/app/integrations/plaid/models.py)): `amount`, `name`
(payee/description), `merchant_name`, `category`, `account_id`.

**`plaid_connections`**: `institution_name` (bank name), `accounts_json` (account names, types, and
the **mask = last 4**), and `encrypted_access_token` (already encrypted before this change).

`accounts_json` is the only cached Plaid API response we store; there is no raw-payload table.

## What is NOT encrypted, and why

| Field | Why kept plaintext |
|---|---|
| `plaid_transactions.date` | Range-filtered (`date_from`/`date_to`) and `ORDER BY date` in `list_transactions`. Encrypting breaks those queries. A transaction date alone (no amount/merchant) is low-sensitivity. **Tradeoff accepted + noted here.** |
| `plaid_transactions.plaid_transaction_id` | `UNIQUE` + used as the dedup/idempotency key on sync (`WHERE plaid_transaction_id = …`). Opaque Plaid id, not consumer financial detail. |
| `plaid_connections.item_id`, `institution_id`, `sync_cursor` | Opaque Plaid identifiers/cursor. `item_id` is `UNIQUE`; `institution_id` is like `ins_109508`. Not consumer financial detail. |
| `is_income`, `is_categorized`, `pending` | Booleans used in `WHERE` filters. Non-sensitive. |
| FKs, `id`, timestamps | Structural / non-sensitive. |

**No full bank account numbers are stored.** Plaid does not return them by default — only a masked
last-4 (in `accounts_json`), which **is** encrypted.

**Out of scope (documented boundary):** once a user *categorizes* a Plaid transaction, an `Expense`
or `Income` row is created in the general **bookkeeping ledger** (`expenses`/`income_entries`). Those
tables are the app-wide accounting ledger — heavily queried and aggregated for financial reports — and
are **not** encrypted here. This change covers the dedicated Plaid tables where raw retrieved data
lands.

## Migration (encrypt existing rows in place)

Shared, idempotent, fail-closed logic in
[at_rest.py](backend/app/integrations/plaid/at_rest.py) (raw SQL, so it bypasses the ORM types and
neither double-encrypts nor fails on plaintext; already-encrypted values are skipped).

- **Automatic (deploy):** Alembic migration
  [e1f2a3b4c5d6](backend/alembic/versions/e1f2a3b4c5d6_encrypt_plaid_at_rest.py) runs during
  `alembic upgrade head` in [deploy.sh](deploy.sh) — which now **backs up the DB first** — so the
  backlog is encrypted *before* the new app restarts. `downgrade()` decrypts back (rollback).
- **Manual / verification:** [scripts/plaid_encrypt_at_rest.py](backend/scripts/plaid_encrypt_at_rest.py):
  ```bash
  cd backend
  .venv/bin/python scripts/plaid_encrypt_at_rest.py            # DRY-RUN, prints before/after counts
  .venv/bin/python scripts/plaid_encrypt_at_rest.py --apply    # backs up (scripts/backup.sh) then encrypts
  .venv/bin/python scripts/plaid_encrypt_at_rest.py --decrypt --apply   # rollback
  ```
  Both refuse to run without `FERNET_KEY` (fail closed) and are safe to re-run (idempotent).

**Rollback:** restore the pre-migration snapshot (`scripts/restore.sh`, see `scripts/BACKUPS.md`), or
run the `--decrypt --apply` reversal / `alembic downgrade`. As of writing, prod has 0 Plaid rows
(Plaid Link is behind its flag), so the first run is effectively a no-op — but the path is proven by
tests on seeded data.

## Performance

- **Write:** ~5 Fernet ops per transaction on sync/insert (microseconds each) — negligible.
- **Read:** decrypt happens per selected row/field. Paged reads (`page_size=50`) decrypt ~250 values
  — trivial. Full-table scans (e.g. `apply_rules_to_all` over all uncategorized txns) decrypt every
  field of every row; still sub-second for tens of thousands of rows, but O(rows). No query regressed
  because every field used in `WHERE`/`ORDER BY`/aggregate was deliberately left plaintext.
- **Storage:** Fernet ciphertext is ~2–3× the plaintext size; columns are `TEXT`.

## Tests

[tests/api/test_plaid_encryption_at_rest.py](backend/tests/api/test_plaid_encryption_at_rest.py):
encrypt-on-write / decrypt-on-read (string + numeric), None handling, legacy-plaintext read tolerance,
**fail-closed when the service/key is absent**, `load_fernet_or_fail` fail-closed, migration
encrypt-in-place + **dry-run** + **idempotency**, and downgrade reversal. Plus an async ORM test that
the real model stores ciphertext. (8 sync tests pass locally; full ORM path validated end-to-end.)

## Plaid questionnaire wording this justifies

> Consumer financial data retrieved from Plaid — transaction amounts, descriptions, merchant names,
> categories, and account identifiers, plus account metadata including the masked account number
> (last 4) — is **encrypted at rest at the application layer** using Fernet (AES-128-CBC with
> HMAC-SHA256 authentication; 128-bit encryption key) before it is written to the database. The
> encryption key is supplied via environment configuration and held outside the database; the
> application refuses to start without it. Plaid access tokens are likewise encrypted at rest. No full
> bank account numbers are stored. A small set of non-sensitive, opaque identifiers and the
> transaction date are retained in plaintext to support required lookups and reporting.
