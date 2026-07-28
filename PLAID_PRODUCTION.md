# Plaid — production go-live (operators only)

Wiring Plaid **production** for the two operators (Nathan `nathano@ocidm.io`,
Shivonne `shivonneo@ocidm.io`) to connect their own real bank accounts. Public /
tenant access stays **OFF**.

---

## 1. The deduplication answer (tax integrity) — READ THIS FIRST

**Does connecting a bank risk silently double-counting a transaction you already
entered by hand?**

- **No dedup existed** between Plaid transactions and manual entries — confirmed
  in code. Plaid transactions live in their own table (`plaid_transactions`),
  separate from the books; the reconciliation module matches *receipts→cashbook*,
  never Plaid.
- **BUT sync does NOT auto-post.** Synced rows land in `plaid_transactions` with
  `is_categorized=False` — inert, in no ledger. So connecting + syncing **cannot**
  double-count. That review buffer already existed.
- The only risk was at the **categorize** step: turning a Plaid transaction into
  an `Expense`/`Income` did not check for a matching manual record.

**What I added** ([backend/app/integrations/plaid/reconcile.py](backend/app/integrations/plaid/reconcile.py)):
- **Manual categorize** — if a likely-duplicate manual entry exists (same amount,
  date within 4 days), the first attempt is refused with **`409
  PLAID_POSSIBLE_DUPLICATE`** carrying the matching record(s). It posts only when
  re-sent with `confirm_duplicate: true`. Flags for confirmation; never
  double-posts by accident.
- **Automatic rules** — a rule that matches is **skipped** (left uncategorized)
  when a likely manual duplicate exists, rather than silently auto-posting.
- **`GET /transactions/{id}/possible-duplicates`** lets the review UI warn before
  the user categorizes.

Match = exact amount **and** date within `DUP_DATE_WINDOW_DAYS` (4). Deliberately
broad: it flags for a human, never auto-merges or deletes. Proven by
[tests/adversarial/test_plaid_prod_gate_dedup.py](backend/tests/adversarial/test_plaid_prod_gate_dedup.py).

---

## 2. Access — operators only (server-enforced)

The Link flow was gated by flag + role (accountant/admin) + MFA — but **role is
not enough**: self-serve signups each become ADMIN of their own tenant, so
flipping the flag alone would open Link to every tenant admin.

Added an **email allow-list** ([config.py](backend/app/config.py) `plaid_link_allowed_emails`),
enforced in `require_plaid_link_access` and reflected in `/link-config`
([router.py](backend/app/integrations/plaid/router.py)). A non-allow-listed
account — including a tenant admin with MFA — gets **`403
PLAID_LINK_NOT_ALLOWLISTED`**.

**To go fully public later (once cyber insurance is in place):** clear
`PLAID_LINK_ALLOWED_EMAILS` (empty = "any accountant/admin with MFA"), leaving
`PLAID_LINK_ENABLED=true` as the master switch. No code change.

**Who can enter the platform keys.** The Plaid production `client_id`/`secret`
are OCIDM's shared **platform** credentials, stored **once** at the platform
level (encrypted, one row in `integration_configs`) — not per tenant. Writing
them via Settings → Banking is **locked to the operator allow-list**
([settings_router.py](backend/app/integrations/settings_router.py), refuses with
`PLAID_CONFIG_OPERATOR_ONLY`): once `PLAID_LINK_ALLOWED_EMAILS` is set, a tenant
admin cannot overwrite the keys. (Empty allow-list = unrestricted, so the very
first keys can be entered before the list exists. Other integrations keep the
role-only gate.)

---

## 3. Safety controls (verified already present, fire on real data)

- **Consent** recorded before connection (hard precondition at exchange; a
  `plaid_consents` row + `PLAID_CONSENT_CAPTURED` audit) — service.py.
- **Encrypted at rest** — access token Fernet-encrypted; transaction
  `amount`/`name`/`merchant`/`category`/`account_id` use `EncryptedString`/
  `EncryptedNumeric`. **`FERNET_KEY` is set on the server (confirmed).**
- **MFA required** to connect *and* to read/sync/categorize bank data
  (`require_plaid_link_access` / `require_financial_data_access`).
- **Disconnect purges** the connection → cascades its transactions; retention job
  purges raw rows nightly past the window.
- **No sandbox paths** (`user_good`, `/sandbox/`) exist in the production flow;
  an unknown `PLAID_ENV` fails safe to Sandbox.

---

## 4. Go-live checklist (the remaining steps need YOUR secrets)

I cannot place production credentials or log into a bank. Plaid config is read
from two places — the runtime prefers the DB (Settings screen) over `.env`:

**A. Platform keys — enter in the app (this is where they take effect).**
Settings → Banking → Plaid Configuration: **Environment = production**, **Client
ID**, **Secret**. Stored encrypted, platform-wide, applied immediately + on
restart; writing is operator-locked (§2). **Nathan enters these once; Siobhan
does not.** *(Equivalently `PLAID_ENV` / `PLAID_CLIENT_ID` / `PLAID_SECRET` in
`.env` — but the Settings-screen values win.)*

**B. Flag + allow-list — set in `.env`** (not part of the Settings screen), then
restart the backend:

```
PLAID_LINK_ALLOWED_EMAILS=nathano@ocidm.io,shivonneo@ocidm.io
PLAID_LINK_ENABLED=true
# FERNET_KEY already set; PLAID_REQUIRE_MFA_FOR_DATA defaults true (leave it)
```

Then verify:
1. Both operators have **MFA enrolled** (passkey or authenticator) — required to connect.
2. Each operator opens Settings → Banking and connects their **own** bank (they
   enter their bank credentials in Plaid's own UI — never elsewhere).
3. A non-operator / tenant account sees **no** Connect option and is refused
   `403 PLAID_LINK_NOT_ALLOWLISTED` at the API.
4. After sync, transactions sit **uncategorized** (review buffer) — nothing posts
   to the books until explicitly categorized, and a categorize that collides with
   a manual entry is flagged, not double-posted.

> **Client (built + deployed):** the "Connect a bank" button (Settings → Banking,
> gated on `/link-config`) and the confirm-duplicate dialog (Bank Transactions)
> are live via `react-plaid-link` — but stay hidden/inert until the flag +
> allow-list are set and Link is enabled.
