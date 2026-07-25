# Plaid Prerequisites — Build Report

Prerequisites required **before Plaid Link is surfaced to any user**, plus two urgent
data-safety fixes. The live "Connect account" button is **not** wired — Plaid Link stays
behind the `plaid_link_enabled` flag (default **OFF**) until consent + MFA + privacy policy
are verified. Everything below is the gating built so it is ready to flip on.

## How this was verified

The dev box runs Python 3.14, on which `pytest-asyncio` crashes/hangs during the app
fixture (the **existing** suite hangs too — it is an environment fault, not the code).
CI runs Python **3.12** (`.github/workflows/ci.yml`) and is the authoritative gate. Locally
verified:

- **7/7** pure unit tests pass: `tests/adversarial/test_fernet_guard.py` + the TOTP/recovery
  primitives in `tests/api/test_mfa.py`.
- **26/26** async service checks pass via a standalone `asyncio.run` harness (bypassing the
  broken pytest-async fixtures) covering audit, MFA enroll/login/recovery, consent
  capture/refusal, retention, and deletion/anonymization.
- **Backup round-trip** smoke test passes (`scripts/backup-smoke-test.sh`).
- **Frontend** typechecks clean (`tsc -b --noEmit`, exit 0); `/privacy` and `/terms` render
  and are publicly reachable (verified in the browser preview).
- Full schema builds (147 tables) with the new tables/columns and no collisions.

Run the full backend suite in CI or on Python 3.12 locally:

```bash
cd backend && python -m pytest tests/adversarial tests/api tests/integration -q
```

---

## URGENT 0a — FERNET_KEY data-loss guard

**What:** `init_encryption_service` now refuses to boot on **any** database (incl. SQLite)
when `FERNET_KEY` is unset, instead of silently generating an ephemeral key that corrupts all
encrypted fields on restart. Exceptions: the test suite, and an explicit local-dev opt-in
`ALLOW_EPHEMERAL_FERNET_KEY=1`. A persistent key logs a confirmation with a non-reversible
fingerprint (never the key).

**Files:** `backend/app/core/encryption.py`. Tests: `backend/tests/adversarial/test_fernet_guard.py`.

**Verify:** `pytest tests/adversarial/test_fernet_guard.py` (4 pass). Or live: running any entrypoint
outside pytest with no key now raises a clear `RuntimeError` (confirmed).

## URGENT 0b — Backups

**What:** `scripts/backup.sh` (online SQLite `.backup` + tar of `data/documents` → timestamped
archive, keep newest `$KEEP`), `scripts/restore.sh` (sandbox + guarded in-place),
`scripts/backup-smoke-test.sh` (seeds → backs up → restores → asserts). Cron + systemd examples
in `scripts/BACKUPS.md` and `scripts/backup.cron.example`.

**Verify:** `bash scripts/backup-smoke-test.sh` → "SMOKE TEST PASSED". Also runs in CI via
`backend/tests/integration/test_backup_restore.py`.

## 1 — Plaid consent capture & persistence

**What:** New `PlaidConsent` model (user, tenant, timestamp, product scope, consent version,
privacy-policy version, exact consent text, IP, linked connection). `exchange_public_token`
now **refuses** to create a connection unless `consent_acknowledged` is true, and writes the
consent row **transactionally** with the connection (single commit). Consent copy is
server-authoritative (`app/core/legal.py`). Platform admins can list consents.

**Files:** `backend/app/integrations/plaid/models.py`, `schemas.py`, `service.py`, `router.py`
(`GET /api/integrations/plaid/admin/consents`), `backend/app/core/legal.py`. Tests:
`backend/tests/api/test_plaid_consent.py`.

**Verify:** async harness checks "exchange refused without consent → nothing created", "consent
linked/versioned/text persisted", "consent capture audited" (all pass).

## 2 — Privacy policy served, linked, versioned

**What:** Public `/privacy` and `/terms` routes/pages (placeholder copy, clearly marked, **not**
invented legal text), versioned. Linked in the **app footer** (`AppShell`) and **at the Plaid
connection UI** (`PlaidSettings`). Backend exposes `GET /api/legal/versions`; the consent record
references `PRIVACY_POLICY_VERSION`.

**Files:** `frontend/src/pages/PrivacyPolicyPage.tsx`, `TermsPage.tsx`, `frontend/src/lib/legal.ts`,
`frontend/src/App.tsx` (routes), `frontend/src/components/layout/AppShell.tsx` (footer),
`frontend/src/components/settings/PlaidSettings.tsx` (link), `backend/app/main.py`
(`/api/legal/versions`). Tests: `backend/tests/integration/test_legal_and_link_config.py`.

**Verify:** `tsc -b --noEmit` clean; `/privacy` + `/terms` render (browser-verified).

## 3 — End-user MFA before Plaid Link

**What:** TOTP MFA (stdlib RFC 6238, no new dependency) with enrollment, confirmation, recovery
codes (shown once, stored hashed), disable, and a two-step login (password → challenge → TOTP or
recovery). MFA secret stored Fernet-encrypted on the user. **Hard gate**: `require_plaid_link_access`
blocks Plaid link-token/exchange unless the flag is on, the role is accountant/admin, **and** MFA
is enabled.

**Files:** `backend/app/auth/mfa.py`, `mfa_service.py`, `mfa_router.py` (`/api/auth/mfa/*`),
`mfa_dependencies.py`, `models.py` (User MFA columns), `service.py` (login MFA branch),
`integrations/plaid/router.py` (gate). Tests: `backend/tests/api/test_mfa.py`.

**Verify:** harness — enrollment/secret-encrypted/challenge/TOTP-login/recovery-single-use all pass;
`test_plaid_consent.py` asserts link-token 403s with `MFA_REQUIRED` when MFA is off.

## 4 — Data retention & deletion

**What:** `POST /api/privacy/me/export` (+ admin variant) returns the user's data as JSON with **no
secrets**. `POST /api/privacy/me/delete` (+ admin variant, confirm `"DELETE"`) hard-deletes financial
+ secret child data (Plaid connections → cascade transactions, Gmail/Calendar tokens, SMTP configs,
refresh/reset tokens) and **irreversibly anonymizes** the user row (`anonymized_at`). Legal-retention
exceptions are documented in code and retained: audit logs, consent records, financial books.
Configurable Plaid retention (`plaid_data_retention_days`, default 0/off) enforced by a scheduler job.
Export/deletion are audited.

**Files:** `backend/app/privacy/service.py`, `router.py`, `schemas.py`, `auth/models.py`
(`anonymized_at`), `core/scheduler.py` (retention job), `config.py`. Tests:
`backend/tests/api/test_privacy_data_rights.py`.

**Verify:** harness — anonymization, connection/token hard-delete, consent retained, deletion audited,
retention prunes only aged rows (all pass).

## 5 — Minimal security audit trail

**What:** New append-only `AuditLog` (`security_audit_logs`; distinct from the existing document
`audit_logs`). Records login success/failure, MFA events, consent capture, Plaid connection, and
data export/deletion — with actor, tenant, action, result, IP, timestamp, metadata. Queryable at
`GET /api/platform-admin/audit` (platform-admin gated). Retention: 730 days (`AUDIT_RETENTION_DAYS`),
pruned by a scheduler job.

**Files:** `backend/app/audit/models.py`, `service.py`, `schemas.py`, `router.py`, plus call sites in
auth/MFA/plaid/privacy services; `core/scheduler.py` (prune job); `main.py` (mount). Tests:
`backend/tests/api/test_audit_log.py`.

**Verify:** harness — login success/failure audited; consent + deletion audited. Admin query +
non-admin 403 covered by `test_audit_log.py` (CI).

---

## 6 — WebAuthn / passkey MFA (added, alongside TOTP)

**What:** Phishing-resistant FIDO2 passkeys as a **second factor that sits beside TOTP** — TOTP is
untouched. Uses the maintained `webauthn` (py_webauthn v3) library — no custom crypto. New
`WebAuthnCredential` model (public key only, sign counter, transports, device name, timestamps; a
user may register many). Registration + authentication ceremonies with server-issued challenges;
the assertion path enforces a **strictly-increasing sign count** to detect cloned authenticators.

**Either factor = MFA:** a single helper `mfa_common.has_mfa` treats "has TOTP **or** ≥1 passkey" as
MFA-enabled. The login flow, the `require_mfa_enabled` dependency, the **Plaid Link gate**
(`require_plaid_link_access`), and `link-config` all use it — so **no existing TOTP user loses Plaid
access**, and a passkey-only user is equally covered. Recovery is unchanged: lose all passkeys →
fall back to TOTP + recovery codes. **No email-a-link passkey reset** (that would reintroduce the
phishing weakness) — documented in the UI.

**Files:** `backend/app/auth/webauthn_models.py`, `webauthn_service.py`, `webauthn_router.py`
(`/api/auth/webauthn/*`), `mfa_common.py`, `mfa_dependencies.py`, `mfa_service.py` (shared token
issuance), `auth/service.py` (login `methods`), `integrations/plaid/router.py` (gate), `config.py`
(`webauthn_*`), `audit/service.py` (3 new actions), `main.py` + `conftest.py` (wiring). Frontend:
`frontend/src/api/webauthn.ts`, `components/settings/PasskeySettings.tsx` (register / name / list /
remove), `pages/SettingsPage.tsx` (Passkeys tab). Tests: `backend/tests/api/test_webauthn.py`.

**⚠️ Config to set before this works on the live domain:** WebAuthn verification fails unless the RP
ID and origin match the deployed domain. In the VPS `backend/.env` set:

```
WEBAUTHN_RP_ID=accountant.ocidm.io        # the registrable domain — NO scheme, NO port
WEBAUTHN_ORIGIN=https://accountant.ocidm.io   # the full origin the browser sees
WEBAUTHN_RP_NAME=O-Brain
```

Dev defaults are `localhost` / `http://localhost:5173`. Passkeys registered under one RP ID do not
work under another, so set these before users enroll. (Also: passkeys require HTTPS in production —
covered by the TLS infra item below.)

**Verify:** 17/17 checks in the standalone async harness (schema, either-factor `has_mfa`,
registration stores public-key-only, assertion updates sign count, **replay/clone rejection**,
audit, passkey-removal fallback). `test_webauthn.py` covers the same plus the login ceremony and the
"passkey OR TOTP satisfies the Plaid gate" cases in CI. Frontend typechecks clean; the passkey tab's
live render wasn't exercised here (auth-gated, needs a running backend — unstable on this box).

## Schema note (deployment)

New **tables** are created by `create_all` on SQLite startup. New **columns on the existing `users`
table** (MFA + `anonymized_at`) are **not** — `create_all` never alters existing tables. Added
`backend/app/core/schema_patch.py`, run on SQLite startup, which idempotently `ALTER TABLE ... ADD
COLUMN`s the missing user columns. **For a Postgres deployment**, generate an Alembic migration for
the new tables/columns instead (migrations are Postgres-only in this repo).

## Still requires infrastructure action (cannot be done in code)

- **TLS floor / HSTS / HTTP→HTTPS redirect** — reverse-proxy/host config (nginx + certbot).
- **At-rest disk/volume encryption** for the SQLite DB + `data/documents` — host/VPS.
- **Production/admin MFA** (SSH, hosting console) — infrastructure.
- **Confirm `FERNET_KEY` is set on the VPS** — the 0a guard now forces this, but the value lives in
  the server `.env`. Set a stable key before the next deploy or the app will (correctly) refuse to boot.
- **External/off-box backups** — `scripts/backup.sh` writes locally; ship archives off the VPS
  (e.g. rclone/aws s3 to the R2 bucket). See `scripts/BACKUPS.md`.

## Follow-ups (not blocking, worth doing)

- Wire the Plaid Link JS SDK + "Connect account" button behind the `link-config.enabled` flag (the
  gate, consent capture, and config endpoint are ready).
- Rate-limit `POST /api/auth/mfa/login` (currently protected only by the 5-min challenge token + audit).
- Extend MFA challenge to the Google-OAuth login path (today the hard Plaid gate covers Google users;
  account-wide MFA at login is enforced only on the password path).
- A concurrent worktree/session is editing shared files (e.g. `User.sub_account_id` in
  `app/operators/`) — coordinate before merging to avoid conflicts.
