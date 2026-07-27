# Twilio Reseller / Subaccount — Operations Notes

Scope of this doc: the two code-level fraud kill switches (usage-trigger
auto-suspend, and the platform-wide circuit breaker) and how to operate them.
The remaining reseller build (provisioning, rate card, A2P, admin console) is
tracked separately; this covers what an operator needs to run the safety
controls.

> **Gate status:** capability enforcement (`telephony_enforce_capabilities`) and
> tenant billable provisioning stay **OFF**. Nothing here opens them.

---

## Kill switch — automatic suspension on a spend breach

**What arms it.** When a subaccount is provisioned (`telephony.ensure_account`),
`create_usage_triggers` registers **two** Twilio Usage Triggers on that
subaccount, both firing `usage_category=totalprice`:

| Trigger | Threshold | `recurring` | Effect |
|---|---|---|---|
| `obrain-daily-spend` | per-tenant daily cap (`daily_spend_cap_usd`, default $10) | daily | **Alert only** — notifies the owner |
| `obrain-monthly-spend` | per-tenant monthly cap (`monthly_spend_cap_usd`, default $100) | monthly | **Alert + auto-suspend** |

Both POST to `POST /api/integrations/sms/usage-trigger`.

**What happens on a breach.** Twilio calls that webhook. The handler:

1. Looks up the subaccount by the `AccountSid` in the payload. Unknown → ignored.
2. **Verifies `X-Twilio-Signature` against THAT subaccount's own auth token.**
   The triggers live on the subaccount, so Twilio signs with the subaccount
   token; forging it requires a token an attacker does not have. An invalid or
   missing signature → **HTTP 403, no suspension** (a spoofed callback cannot
   nuke a tenant).
3. On a valid **monthly** breach: calls `telephony.suspend()`, which suspends
   the subaccount at Twilio (server-side enforcement), records it locally,
   **writes a `telephony_suspended` security-audit row** (actor
   `system:usage-trigger`), and notifies the owner. A **daily** breach only
   alerts.

Once suspended, every outbound/provisioning path refuses automatically, because
they all resolve credentials through `ensure_account`, which raises
`TelephonySuspended`. **Inbound is unaffected** — receiving SMS/calls does not
touch the suspension gate.

## Reactivation (reversing the kill switch)

Operator-only, from platform admin:

```
POST /api/platform-admin/telephony/accounts/{account_id}/reactivate
```

It re-enables the Twilio subaccount and writes a `telephony_reactivated` audit
row with the operator's email. The matching manual suspend is
`POST /api/platform-admin/telephony/accounts/{account_id}/suspend`.

Audit trail: query `security_audit_logs` for `action in
('telephony_suspended','telephony_reactivated')`.

---

## Platform-wide circuit breaker

A single aggregate ceiling across **all** tenants, independent of per-tenant
caps. When today's total telephony spend (read from Twilio) is at or above the
ceiling, new **outbound SMS**, **outbound voice**, and **number purchases** are
refused with **HTTP 503 `TELEPHONY_CIRCUIT_OPEN`** (a clear response, not a
silent drop). Inbound is unaffected.

- **Config:** `PLATFORM_DAILY_SPEND_CEILING_USD` in
  `app/communication/telephony.py` (default **$250/day**).
- **Enforcement point:** `telephony.enforce_billable_action()`, called before
  the billable action on the send + purchase paths. (The number-purchase check
  is a guard inside `enforce_billable_action`, added without touching the
  streaming code at `router.py:1222`.)
- **Fail-open on read errors:** if Twilio's usage API is unreachable the breaker
  *allows* traffic, on the reasoning that an outage should not take telephony
  down for everyone and the per-tenant caps + prepaid credit still bind. This is
  a deliberate trade-off; flip to fail-closed here if you prefer provisioning to
  stop during a Twilio outage.

---

## Per-tenant caps (unchanged, still enforced)

Independent of the platform breaker, each tenant has a daily and monthly cap
(`daily_spend_cap_usd` / `monthly_spend_cap_usd` on `telephony_accounts`; NULL →
the module defaults above). `telephony_credits.enforce_spend_caps` blocks
outbound with **HTTP 402 `TELEPHONY_CAP_REACHED`** once ledger spend crosses the
cap. Raise a specific tenant's cap by setting the column on its
`telephony_accounts` row.

---

## Least-privilege capabilities (Step 0 final gate)

Every billable telephony action requires an **operator-granted** capability on
the tenant's subaccount, all **default OFF**:

| Capability column | Gates |
|---|---|
| `allow_number_purchase` | buying a phone number (`number_purchase`) |
| `allow_sms` / `allow_mms` | outbound SMS / MMS |
| `allow_voice_outbound` / `allow_voice_inbound` | outbound / inbound voice |
| `allow_markup` | operator may set retail above cost (Step 5) |

Columns live on `telephony_accounts` (migration `f2a3b4c5d6e7`, plus the additive
SQLite patch in `app/core/schema_patch.py`) — no new migration is needed.

**Only an operator grants them** (`require_platform_admin`):
`PUT /api/integrations/sms/telephony/capabilities/{tenant_key}`. A tenant admin
calling it gets 403 — **no self-escalation**. Enforcement is server-side in
`telephony.enforce_billable_action` on outbound SMS, outbound voice, and number
purchase; a missing grant → **403 `TELEPHONY_CAPABILITY_NOT_GRANTED`** before the
billable action.

**No self-provisioning.** When enforcement is ON, `enforce_billable_action`
checks the capability with `get_account` (which never creates) *before* anything
is provisioned — so an ungranted tenant hitting a billable endpoint is refused
and **no subaccount is auto-created**. A subaccount comes into existence ONLY via
the operator-only provision endpoint below.

### The `telephony_enforce_capabilities` flag

- **OFF (current, and the prod default): PERMISSIONLESS.** Grants are recorded
  but not enforced — a provisioned tenant can act without a grant (only a
  warning is logged). **Do not run production with real tenants while OFF.**
- **ON:** enforced as above.

## Go-live order — walk it IN THIS ORDER; keep provisioning closed until then

1. **Operator provisions** the tenant's subaccount (operator-only; tenants
   cannot self-provision):
   `POST /api/platform-admin/telephony/accounts/provision {"user_id": "<tenant owner>"}`.
   This creates the subaccount, applies geo, arms the usage triggers, and enables
   pumping protection. Idempotent.
2. **Operator grants** the exact capabilities that tenant should have:
   `PUT /api/integrations/sms/telephony/capabilities/{tenant_key}`.
3. **Flip `telephony_enforce_capabilities` ON.**
4. **Only now** do purchase / SMS / voice work for that tenant — and still only
   within the per-tenant caps, prepaid credit, and platform circuit breaker.

Until this order is walked for a tenant, that tenant has nothing granted, so with
the flag ON it can do nothing billable and cannot provision itself.

---

## Kill-switch / circuit-breaker go-live (safety controls)

1. Confirm `public_base_url` is the real HTTPS origin — the usage-trigger
   callback URL is built from it, and a wrong value silently disarms the kill
   switch.
2. Provision each tenant's subaccount (step 1 above) so `create_usage_triggers`
   runs (arms both triggers).
3. Verify a signed test callback suspends and an unsigned/invalid one is
   refused (covered by `tests/adversarial/test_telephony_kill_switch.py`).
4. Set `PLATFORM_DAILY_SPEND_CEILING_USD` to your real aggregate ceiling.
5. Leave `telephony_enforce_capabilities` OFF until subaccounts + grants exist,
   then flip it per the go-live order above.
