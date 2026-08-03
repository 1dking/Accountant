# Production backups

Backs up the production **SQLite DB** (`backend/data/accountant.db`) and the
**uploaded-files directory** (`backend/data/documents`) to timestamped archives,
with a retention window. See `backup.sh`, `restore.sh`, `backup-smoke-test.sh`.

## One-off

```bash
bash scripts/backup.sh
# -> writes ./backups/accountant-YYYYmmdd-HHMMSS.tar.gz, keeps newest $KEEP (14)
```

Override anything via env:

```bash
BACKUP_DEST=/mnt/backups KEEP=30 bash scripts/backup.sh
```

## Verify it restores (do this — an untested backup is not a backup)

```bash
bash scripts/backup-smoke-test.sh
# seeds a throwaway DB + file, backs up, restores into a temp dir, asserts equality
```

This also runs in CI (see `.github/workflows/ci.yml`).

## Schedule it

### Option A — cron (simplest)

`crontab -e` on the VPS and add (off-box upload is automatic via the R2 config in
`backend/.env`):

```cron
# Daily at 04:30 — snapshot + off-box to R2, keep newest 14, log to a file
30 4 * * * cd /home/dh_pjj4dt/Accountant && KEEP=14 bash scripts/backup.sh >> /home/dh_pjj4dt/Accountant/logs/backup.log 2>&1
```

This runs **independently of deploys** (deploys also snapshot, but only when you
deploy). Check it ran: `tail ~/Accountant/logs/backup.log`.

### Option B — systemd timer

`/etc/systemd/system/accountant-backup.service`:

```ini
[Unit]
Description=Accountant backup

[Service]
Type=oneshot
User=<vps-user>
WorkingDirectory=/home/<vps-user>/Accountant
Environment=KEEP=14
ExecStart=/usr/bin/bash scripts/backup.sh
```

`/etc/systemd/system/accountant-backup.timer`:

```ini
[Unit]
Description=Run Accountant backup daily

[Timer]
OnCalendar=*-*-* 02:15:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now accountant-backup.timer
```

## Restore

Sandbox (safe — inspect before committing):

```bash
bash scripts/restore.sh backups/accountant-YYYYmmdd-HHMMSS.tar.gz /tmp/restore-check
```

In-place (overwrites live data — stop the app first):

```bash
bash stop.sh
CONFIRM=yes bash scripts/restore.sh backups/accountant-YYYYmmdd-HHMMSS.tar.gz
bash start.sh
```

## Off-box copies (built in)

`backup.sh` ships each archive **off the box** to S3-compatible object storage, so
a VPS/disk loss doesn't take the backups with it. If unconfigured it logs a loud
warning and stays local-only (so CI / the smoke test are unaffected).

- **Default:** reuses the Cloudflare **R2** config already in `backend/.env`
  (`R2_ACCESS_KEY_ID/SECRET/BUCKET/ENDPOINT`) and uploads under the `db-backups/`
  prefix. Nothing else to set.
- **Override:** point anywhere S3-compatible (AWS S3, Backblaze B2, Wasabi):
  ```bash
  BACKUP_S3_DEST=s3://my-bucket/accountant \
  BACKUP_S3_ENDPOINT=https://s3.us-west-002.backblazeb2.com \
  AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
  bash scripts/backup.sh
  ```
- Credentials are read from the environment or `backend/.env` and passed to `aws`
  inline — **never hardcoded in the script and never logged**. Remote retention
  keeps the newest `REMOTE_KEEP` (defaults to `KEEP`).
- Verify a copy landed:
  ```bash
  AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=auto \
    aws s3 ls s3://<bucket>/db-backups/ --endpoint-url <R2_ENDPOINT>
  ```

## The FERNET_KEY is NOT in the backup — back it up separately

By design, the archive contains the **encrypted** DB but **not** `FERNET_KEY` (a
stolen backup must not be decryptable). A restored DB is useless without the key,
and the app **refuses to boot** without it (`app/core/encryption.py`). Store the
key **separately and off-box** (password manager / sealed secret). Full disaster
steps: **`scripts/RECOVERY.md`**.
