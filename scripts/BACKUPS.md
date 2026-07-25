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

`crontab -e` on the VPS and add (see `backup.cron.example`):

```cron
# Daily at 02:15, keep 14 days, log to a file
15 2 * * * cd /home/<vps-user>/Accountant && KEEP=14 bash scripts/backup.sh >> /home/<vps-user>/Accountant/logs/backup.log 2>&1
```

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

## Off-box copies (do this too)

These archives live on the same VPS as the data. Ship them off-box on a
schedule — e.g. `rclone copy` / `aws s3 cp` the `backups/` dir to the Cloudflare
R2 bucket already configured in `backend/.env`, or to any offsite target. That
step is infrastructure and is **not** in this repo.
