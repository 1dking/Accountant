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

I cannot place production credentials or log into a bank. On the server
(`~/Accountant/backend/.env`), add — **secrets from the Plaid dashboard, never
committed, never client-side:**

```
PLAID_ENV=production
PLAID_CLIENT_ID=<your production client_id>
PLAID_SECRET=<your production secret>
PLAID_LINK_ALLOWED_EMAILS=nathano@ocidm.io,shivonneo@ocidm.io
PLAID_LINK_ENABLED=true
# FERNET_KEY already set; PLAID_REQUIRE_MFA_FOR_DATA defaults true (leave it)
```

Then restart the backend. Verify:
1. Both operators have **MFA enrolled** (passkey or authenticator) — required to connect.
2. Each operator opens Settings → Banking and connects their **own** bank (they
   enter their bank credentials in Plaid's own UI — never elsewhere).
3. A non-operator / tenant account sees **no** Connect option and is refused
   `403 PLAID_LINK_NOT_ALLOWLISTED` at the API.
4. After sync, transactions sit **uncategorized** (review buffer) — nothing posts
   to the books until explicitly categorized, and a categorize that collides with
   a manual entry is flagged, not double-posted.

> **Frontend note:** the "Connect a bank" button is not yet built on the client
> (`react-plaid-link` is not installed). The backend + gating + dedup are ready;
> building the button is the remaining client task and needs that dependency.
