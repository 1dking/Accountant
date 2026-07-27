# Security Maintenance & Vulnerability Management

How dependency vulnerabilities are found, triaged, and fixed. This is the
running practice a Plaid / InfoSec questionnaire can point at.

## What runs, and when

| Tool | Where | Cadence | Fails build? |
|---|---|---|---|
| **Dependabot** ([.github/dependabot.yml](.github/dependabot.yml)) | pip `/backend`, npm `/frontend`, `/backend/hocuspocus`, `/pricing-lab`, github-actions | Weekly (Mon), grouped minor+patch; **security updates promptly** | opens PRs |
| **Trivy** fs/dependency scan ([security-scan.yml](.github/workflows/security-scan.yml)) | whole repo (lockfiles) | push, PR, weekly (Mon 06:00 UTC) | **yes** — HIGH/CRITICAL |
| **pip-audit** | `backend/requirements.txt` (pinned) | push, PR, weekly | **yes** — any known CVE |
| **pnpm audit** `--audit-level high` | `frontend` | push, PR, weekly | **yes** — HIGH/CRITICAL |

Findings are visible in **CI (Actions)** and, where the repo has code scanning
(public repo or GitHub Advanced Security), in the **Security tab** via the SARIF
Trivy uploads.

## Reproducible scanning

Backend deps are declared as `>=` ranges in `backend/pyproject.toml` but **pinned**
in [backend/requirements.txt](backend/requirements.txt) (exact versions resolved
in production). Scans run against the pinned file so results are exact and
reproducible. Regenerate it after an intentional dependency change (command in
the file header). Dependabot watches both. Frontend/hocuspocus/pricing-lab are
pinned by their lockfiles (`pnpm-lock.yaml` / `package-lock.json`).

## Who reviews, and the patch SLA

- **Reviewer:** Nate (nathano@ocidm.com), OCIDM — reviews Dependabot PRs and CI
  security failures. Grouped minor/patch PRs can be merged after CI is green;
  major-version PRs get a manual check for breaking changes.
- **Patch SLA (from disclosure / alert):**
  - **Critical: 7 days**
  - **High: 30 days**
  - Medium/Low: next scheduled dependency update (weekly cycle).
- **Accepting a finding** (no fix available, or not reachable in our usage):
  add its ID to [.trivyignore](.trivyignore) (Trivy) or `--ignore-vuln <id>` in
  the pip-audit step, **with a justification and a re-review date**. Keep the
  allowlist short.

### Currently accepted advisories

| ID | Package | Justification | Accepted | Re-review |
|---|---|---|---|---|
| `PYSEC-2026-1325` (pip-audit)<br>`CVE-2024-23342` (Trivy) | `ecdsa` | **No fix exists** — upstream considers side-channel (Minerva timing) attacks out of scope. **Not reachable**: `ecdsa` is transitive via `python-jose` only; we sign JWTs with **HS256** (symmetric HMAC, `app/config.py`), so the affected `ecdsa.SigningKey.sign_digest()` / P-256 path is never called. | 2026-07-26 | 2026-10-26 |

> Note: the two scanners use different ID schemes for the same advisory, so an
> accepted finding must be listed in **both** `.trivyignore` (CVE id) and the
> pip-audit `--ignore-vuln` flag (PYSEC id).

## Data retention — enforced, not just documented

Privacy Policy §9 is mechanically enforced, so the commitments are demonstrable:

| Data | Promise (§9) | Enforcement |
|---|---|---|
| Raw Plaid bank rows | Deleted when no longer needed | Nightly job, `PLAID_DATA_RETENTION_DAYS` (default **2555 = 7 years**, the §9 outer bound). `app/core/scheduler.py` → `privacy.service.enforce_plaid_retention`; each purge writes a `data_deleted` audit row |
| Bank connection data | Deleted **on disconnect** / account closure | Immediate, via `ondelete="CASCADE"` on `PlaidTransaction.plaid_connection_id`; also covered by the deletion path in `app/privacy/service.py` |
| Bookkeeping records (expenses/income/invoices) | Retained for the statutory 6–7 years | **Deliberately untouched** by the retention job — verified by test |
| Consent records | Retained as proof | Excluded from deletion; connection link nulled |
| Security audit log | 730 days | `prune_audit_logs` nightly |

Guard: a window under **30 days** is refused as a likely typo (it would wipe live
bank data on the next nightly run) — set it deliberately, or `0` to disable.
Tests: `backend/tests/api/test_retention_policy.py`.

**Not automated:** purging bookkeeping records *after* the 6–7 year statutory
period. Nothing in the system is near that age yet; when it matters this needs a
deliberate ledger-archival design rather than a nightly delete.

## Quarterly EOL / end-of-life review

Every quarter, confirm none of the runtime platforms is near or past
end-of-life, and plan the upgrade if so:

- **Python** — prod runs **3.10** (VPS venv); CI runs **3.12**. Python 3.10
  security support ends **Oct 2026** — plan the move to 3.12/3.13 before then.
- **Node.js** — CI/build uses **Node 20** (LTS). Track its LTS end date.
- **Base OS** — the DreamHost VPS OS + system OpenSSL/glibc; also GitHub Actions
  `ubuntu-latest`. Confirm the VPS OS is receiving security updates.
- **Key third-party SDKs** — Plaid, Stripe, Twilio, LiveKit client/server
  versions vs their supported ranges.

Record each quarterly review (date + who) in the PR that bumps anything, or in a
short note here.

## Incident quick-reference

1. Alert fires (Dependabot / CI red / Security tab).
2. Triage severity → apply the SLA above.
3. Fix = merge the Dependabot PR (or bump + regenerate `requirements.txt`), or
   accept with justification in the allowlist.
4. Confirm the Security Scan workflow is green again.
