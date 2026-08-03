# Disaster recovery — rebuild on a fresh box

What to do if the VPS is lost. The goal: a working app whose **encrypted bank data
decrypts**. That requires TWO things stored in TWO different places:

1. **The data** — the backup archive (`accountant-*.tar.gz`), shipped off-box by
   `backup.sh` to Cloudflare R2 (or your configured S3 bucket).
2. **The key** — `FERNET_KEY`, which is **deliberately NOT in the backup**. A
   backup with the key inside would defeat encryption (a stolen tarball would be
   readable). The key lives **separately** in a password manager / sealed secret.

> ⚠️ **Without the FERNET_KEY, the restored database is permanently undecryptable.**
> The backup and the key are a pair; neither is useful alone. Keep the key in a
> place that survives the loss of the VPS **and** is not the same place as the
> backups.

The app enforces this: it **refuses to boot** without `FERNET_KEY`
(`app/core/encryption.py` → `init_encryption_service`, raises "Refusing to boot").
So a keyless restore fails loudly at startup, never silently with corrupt data.

---

## What you need before you start

- [ ] Access to the **off-box backups** (R2/S3 bucket) — read the R2 credentials.
- [ ] The **`FERNET_KEY`** value from your password manager / sealed secret.
- [ ] The rest of `backend/.env` (R2 creds, Plaid is restored from the DB, Anthropic
      key, etc.). Keep a copy of `.env` off-box too — it is not in the backup.

## Steps

### 1. Fresh box + code
```bash
git clone https://github.com/1dking/Accountant.git ~/Accountant
cd ~/Accountant/backend
python3 -m venv .venv && .venv/bin/pip install -e . && .venv/bin/pip install -r requirements.txt
```

### 2. Get the latest backup off-box
Using the R2/S3 credentials (endpoint + keys), list and download the newest archive:
```bash
# R2 example — fill in from your password manager, do not commit these
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=auto \
  aws s3 ls s3://<bucket>/db-backups/ --endpoint-url https://<acct>.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=auto \
  aws s3 cp s3://<bucket>/db-backups/accountant-YYYYmmdd-HHMMSS.tar.gz ~/Accountant/backups/ \
  --endpoint-url https://<acct>.r2.cloudflarestorage.com
```

### 3. Restore the DB + uploaded files (in place)
```bash
cd ~/Accountant
CONFIRM=yes bash scripts/restore.sh backups/accountant-YYYYmmdd-HHMMSS.tar.gz
```

### 4. Supply the key + config (the part that is NOT in the backup)
Create `backend/.env` and set **at minimum**:
```
FERNET_KEY=<the exact key from your password manager — never regenerate>
```
plus the R2 keys, `ANTHROPIC_API_KEY`, `PLAID_LINK_ENABLED`, `PLAID_LINK_ALLOWED_EMAILS`,
`PLAID_CONFIG_MANAGER_EMAIL`, and `PUBLIC_BASE_URL`. (Plaid API keys are restored
**inside the database** — `integration_configs` — so they come back with the DB.)

### 5. Start and verify it decrypts
```bash
cd ~/Accountant && bash start.sh
```
- If `FERNET_KEY` is wrong/missing the app **won't start** — that's the guard working.
- Health: `curl -s http://127.0.0.1:8000/api/system/health`
- Confirm a real Plaid row decrypts (proves key + data reunited):
```bash
cd ~/Accountant/backend && .venv/bin/python - <<'PY'
import sqlite3
from app.config import Settings
from app.core.encryption import init_encryption_service, get_encryption_service
s=Settings(); init_encryption_service(s.fernet_key)   # never prints the key
svc=get_encryption_service()
c=sqlite3.connect("data/accountant.db")
ct=c.execute("SELECT name FROM plaid_transactions WHERE name IS NOT NULL LIMIT 1").fetchone()[0]
pt=svc.decrypt(ct)
print("decrypt OK — name length:", len(pt))   # a real length => key + backup match
PY
```
If that prints a length, you're recovered. If it raises `InvalidToken`, the
`FERNET_KEY` does not match this backup — get the correct key.

### 6. Confirm the startup log
The boot log should show the resolved Plaid environment (see `app/main.py`):
```
Plaid config resolved: environment=production keys_present=True link_enabled=True
```
`environment=sandbox` or `keys_present=False` after a restore means the Plaid
config didn't come back — re-check the DB restore.

---

## Backing up the key itself (do this now, once)

`FERNET_KEY` is a single line in `backend/.env`. Copy that value into a password
manager entry (e.g. "Accountant FERNET_KEY — prod") and/or a sealed offline note.
Verify the fingerprint matches what the running app logs at boot
("Encryption service initialized ... fingerprint=XXXXXXXX") so you know the stored
copy is the live key. **Never** paste it into a commit, a ticket, or a chat.
