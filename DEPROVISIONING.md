# De-provisioning — one action to revoke access

When someone **leaves the team** or **changes role**, run the de-provisioning
action. It revokes everything it can through an API in a single audited run, and
prints a dated **manual checklist** for the systems it can't reach. This exists
so access removal is never ad-hoc and never partial.

> **Trigger it on _any_ departure or role change.** Do not hand-edit individual
> systems — that is how access gets missed. One action, one audit row.

---

## What it does

Core code: [`backend/app/platform_admin/deprovision.py`](backend/app/platform_admin/deprovision.py)
(`deprovision_user` / `transfer_user`). Operator-only, two ways to run it:

| Surface | How |
|---|---|
| **CLI** (on the server) | `backend/scripts/deprovision_user.py` |
| **API** (platform admin) | `POST /api/platform-admin/users/{id}/deprovision` and `.../transfer` — gated by `require_platform_admin` |

Both go through the same audited path and write a `security_audit_logs` row.

### CLI

```bash
# Departure — full removal
cd ~/Accountant/backend
.venv/bin/python scripts/deprovision_user.py alice@example.com \
    --actor nathano@ocidm.io --github-username alice-gh --reason "left the team"

# Transfer — role change (revoke old access, grant new), same audited path
.venv/bin/python scripts/deprovision_user.py alice@example.com \
    --actor nathano@ocidm.io --transfer --new-role manager --reason "promoted"
```

`--actor` must resolve to an **ADMIN** or an email in `SUPER_ADMIN_EMAILS`, or the
command refuses. It prints a JSON summary of what was revoked, then the manual
checklist.

---

## Automated (done in one run)

| System | Action |
|---|---|
| **O-Brain account** | `is_active = False` — blocks login immediately |
| **Sessions** | ALL active refresh tokens revoked (reuses `revoke_all_user_sessions`) — every logged-in device is kicked |
| **MFA / TOTP** | secret, recovery codes, and enrolment cleared |
| **Passkeys** | every WebAuthn credential row deleted |
| **Role** | downgraded to `VIEWER` (departure) or set to the new role (transfer) |
| **Feature access** | cleared (departure) or replaced (transfer) |
| **Telephony capabilities** | every grant on the tenant's subaccount (`allow_sms`, `allow_voice_*`, `allow_number_purchase`, `allow_mms`, `allow_markup`) turned OFF |
| **GitHub** | removed as a collaborator on every configured repo (best-effort, per-repo outcome recorded) |
| **Audit** | one `user_deprovisioned` / `user_access_transferred` row: who, whom, when, and which systems were revoked |

### Safety guards (can't lock yourself out)

Two guards run before anything is revoked, on **both** the departure and the
role-change paths:

1. **No self-targeting** — the actor cannot de-provision or transfer their own
   account. Ask another operator.
2. **No last-operator lockout** — the action is refused if it would leave the
   platform with **zero active operators**. An operator is an active `ADMIN` or
   an active email in `SUPER_ADMIN_EMAILS` (same definition as
   `require_platform_admin`). The sole/last operator therefore cannot be
   de-provisioned, nor downgraded out of admin by a transfer, unless another
   operator exists first. This is enforced at the service layer independently of
   who the actor is — a second line of defence behind the operator gate.

### GitHub configuration

Set in the server `.env` (see [`backend/app/config.py`](backend/app/config.py)):

```
GITHUB_TOKEN=ghp_xxx            # token with admin on the repos (needed to DELETE collaborators)
GITHUB_REPOS=owner/repo1,owner/repo2
```

Pass the person's handle with `--github-username` (API: `github_username`). If the
token/repos aren't configured or no handle is given, GitHub removal is **skipped
and moved to the manual checklist** — nothing fails silently. A `404` from GitHub
(already not a collaborator) is treated as success. Client:
[`backend/app/integrations/github/client.py`](backend/app/integrations/github/client.py).

---

## Manual checklist (systems with no API in our control)

The action prints a **dated** checklist the operator must complete. These are
surfaced, not automated, so the procedure still covers everything:

- **SSH keys on the VPS** — remove the person's public key from
  `~/.ssh/authorized_keys` for every shell account they could reach.
- **DreamHost panel** — remove the user / revoke shared panel access.
- **Twilio Console** — remove their seat / rotate any credentials they held.
- **Plaid Dashboard** — remove their team seat.
- **Stripe Dashboard** — remove their team member seat.
- **`.env` allow-lists** — if the departing email is in `TELEPHONY_EXEMPT_EMAILS`
  or `SUPER_ADMIN_EMAILS`, the action **detects it and lists it as a required
  step** (these are env config, edited on the server + a restart — not runtime
  DB state, so they cannot be changed from within the app).
- **Shared secrets** — rotate anything the person knew if their departure
  warrants it.

For a **transfer**, the checklist is lighter: re-grant only the telephony
capabilities and console seats appropriate to the *new* role (all were revoked;
nothing is assumed).

---

## Audit trail

Every run writes to `security_audit_logs`. Query it:

```sql
SELECT created_at, actor_email, resource_id, metadata_json
FROM security_audit_logs
WHERE action IN ('user_deprovisioned', 'user_access_transferred')
ORDER BY created_at DESC;
```

`metadata_json` records the target email, the reason, the per-system revocation
result, and the manual-checklist warnings. Rows are retained for
`AUDIT_RETENTION_DAYS` (2 years).

---

## Tests

[`backend/tests/adversarial/test_deprovision.py`](backend/tests/adversarial/test_deprovision.py)
proves: user deactivated, all sessions revoked, role/features/MFA/passkeys
cleared, telephony capabilities revoked, audit row written, GitHub call made
(per repo), the manual checklist is dated and complete, env allow-lists are
flagged, the self-guard, the **last-operator lockout guard** (sole admin /
sole super-admin-email cannot be de-provisioned or downgraded; still works when
another operator remains), the transfer path, the GitHub client's URL/status
handling, and that the endpoint is operator-only (403 for non-admins).

```bash
cd backend && .venv/bin/python -m pytest tests/adversarial/test_deprovision.py -q
```
