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

## Go-live checklist (safety controls only)

1. Confirm `public_base_url` is the real HTTPS origin — the usage-trigger
   callback URL is built from it, and a wrong value silently disarms the kill
   switch.
2. Provision each tenant's subaccount so `create_usage_triggers` runs (arms both
   triggers).
3. Verify a signed test callback suspends and an unsigned/invalid one is
   refused (covered by `tests/adversarial/test_telephony_kill_switch.py`).
4. Set `PLATFORM_DAILY_SPEND_CEILING_USD` to your real aggregate ceiling.
5. Leave `telephony_enforce_capabilities` OFF until subaccounts + grants exist.
