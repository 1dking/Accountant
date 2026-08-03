#!/usr/bin/env bash
# backup.sh — Snapshot the production SQLite DB + uploaded files, and ship a copy
#             OFF the box so a VPS/disk loss doesn't take the backups with it.
#
# Produces a single timestamped tarball in $BACKUP_DEST containing:
#   - accountant.db      (consistent online snapshot via SQLite .backup)
#   - documents.tar.gz   (the uploaded-files directory)
#   - manifest.txt       (what/when)
# then (if configured) uploads it to S3-compatible object storage and prunes old
# archives locally and remotely.
#
# IMPORTANT — the archive does NOT contain FERNET_KEY, by design: a stolen backup
# must not be decryptable. The key is backed up SEPARATELY and off-box (a password
# manager / sealed secret). A restored DB is undecryptable without it, and the app
# refuses to boot without it (app/core/encryption.py:init_encryption_service).
# See scripts/RECOVERY.md.
#
# Config (all overridable via env):
#   DB_PATH       path to the live SQLite DB   (default backend/data/accountant.db)
#   DOCS_DIR      uploaded files directory     (default backend/data/documents)
#   BACKUP_DEST   where archives are written   (default <repo>/backups)
#   KEEP          local archives to retain     (default 14)
#   -- off-box (optional; if unset, logs a warning and stays local-only) --
#   BACKUP_S3_DEST      s3://bucket/prefix destination (e.g. s3://backups/accountant)
#   BACKUP_S3_ENDPOINT  endpoint URL for non-AWS S3 (Cloudflare R2 / B2 / Wasabi)
#   REMOTE_KEEP         remote archives to retain (default = KEEP)
#   ENV_FILE            path to backend/.env for R2 fallback (default backend/.env)
#   If BACKUP_S3_DEST is unset, falls back to the app's Cloudflare R2 config in
#   backend/.env (R2_* keys) under the prefix db-backups/. Credentials are read
#   from the environment or that .env and passed to `aws` inline — NEVER hardcoded
#   here and NEVER logged.
#
# Restore with restore.sh. See scripts/BACKUPS.md + scripts/RECOVERY.md.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${DB_PATH:-$APP_DIR/backend/data/accountant.db}"
DOCS_DIR="${DOCS_DIR:-$APP_DIR/backend/data/documents}"
BACKUP_DEST="${BACKUP_DEST:-$APP_DIR/backups}"
KEEP="${KEEP:-14}"

TS="$(date +%Y%m%d-%H%M%S)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$BACKUP_DEST"

# 1. Consistent SQLite snapshot. `.backup` is an online copy — safe while the
#    app is running and holding the DB open (unlike a raw cp mid-write).
if [ -f "$DB_PATH" ]; then
    if command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 "$DB_PATH" ".backup '$WORK/accountant.db'"
    else
        python3 - "$DB_PATH" "$WORK/accountant.db" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(src)
d = sqlite3.connect(dst)
with d:
    s.backup(d)
s.close(); d.close()
PY
    fi
else
    echo "WARN: DB not found at $DB_PATH — skipping DB snapshot"
fi

# 2. Uploaded files.
if [ -d "$DOCS_DIR" ]; then
    tar -czf "$WORK/documents.tar.gz" -C "$(dirname "$DOCS_DIR")" "$(basename "$DOCS_DIR")"
else
    echo "WARN: docs dir not found at $DOCS_DIR — skipping files"
fi

# 3. Manifest.
{
    echo "created_at=$(date -u +%FT%TZ)"
    echo "db_path=$DB_PATH"
    echo "docs_dir=$DOCS_DIR"
    echo "host=$(hostname 2>/dev/null || echo unknown)"
} > "$WORK/manifest.txt"

# 4. Bundle.
ARCHIVE="$BACKUP_DEST/accountant-$TS.tar.gz"
tar -czf "$ARCHIVE" -C "$WORK" .
echo "Backup written: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# 5. Retention: keep only the newest $KEEP archives locally.
mapfile -t OLD < <(ls -1t "$BACKUP_DEST"/accountant-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))")
for old in "${OLD[@]:-}"; do
    [ -n "$old" ] || continue
    rm -f "$old"
    echo "Pruned old backup: $old"
done

# 6. Off-box copy to S3-compatible object storage. The local tarball sits on the
#    SAME disk as the data; this copy is what survives a VPS/disk loss.
ENV_FILE="${ENV_FILE:-$APP_DIR/backend/.env}"
_envget() {  # print one KEY's value from .env; never echoed elsewhere
    [ -f "$ENV_FILE" ] || return 0
    sed -n "s/^$1=//p" "$ENV_FILE" | head -1 \
        | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//" | tr -d '\r'
}

OFF_DEST="${BACKUP_S3_DEST:-}"
OFF_ENDPOINT="${BACKUP_S3_ENDPOINT:-}"
OFF_AK="${AWS_ACCESS_KEY_ID:-}"
OFF_SK="${AWS_SECRET_ACCESS_KEY:-}"
OFF_REGION="${AWS_DEFAULT_REGION:-auto}"

if [ -z "$OFF_DEST" ]; then
    # Fall back to the app's Cloudflare R2 config already in backend/.env.
    _r2b="$(_envget R2_BUCKET_NAME)"; _r2e="$(_envget R2_ENDPOINT)"
    if [ -n "$_r2b" ] && [ -n "$_r2e" ]; then
        OFF_DEST="s3://$_r2b/db-backups"
        OFF_ENDPOINT="$_r2e"
        OFF_AK="$(_envget R2_ACCESS_KEY_ID)"
        OFF_SK="$(_envget R2_SECRET_ACCESS_KEY)"
    fi
fi

if [ -z "$OFF_DEST" ]; then
    echo "WARN: off-box backup NOT configured (set BACKUP_S3_DEST, or R2_* in backend/.env)."
    echo "      Local-only backup — this is NOT disaster-safe. See scripts/RECOVERY.md."
elif ! command -v aws >/dev/null 2>&1; then
    echo "WARN: aws CLI not found — cannot ship off-box. Local-only backup (not disaster-safe)."
else
    ep=()
    [ -n "$OFF_ENDPOINT" ] && ep=(--endpoint-url "$OFF_ENDPOINT")
    key="$(basename "$ARCHIVE")"
    echo "Off-box: uploading $key -> $OFF_DEST/ (credentials not shown)"
    if AWS_ACCESS_KEY_ID="$OFF_AK" AWS_SECRET_ACCESS_KEY="$OFF_SK" AWS_DEFAULT_REGION="$OFF_REGION" \
            aws s3 cp "$ARCHIVE" "$OFF_DEST/$key" "${ep[@]}" --only-show-errors; then
        echo "Off-box: uploaded $key"
        # Remote retention: keep only the newest $REMOTE_KEEP.
        RK="${REMOTE_KEEP:-$KEEP}"
        mapfile -t RKEYS < <(AWS_ACCESS_KEY_ID="$OFF_AK" AWS_SECRET_ACCESS_KEY="$OFF_SK" AWS_DEFAULT_REGION="$OFF_REGION" \
            aws s3 ls "$OFF_DEST/" "${ep[@]}" 2>/dev/null | awk '{print $4}' \
            | grep -E '^accountant-.*\.tar\.gz$' | sort | head -n "-$RK" || true)
        for rk in "${RKEYS[@]:-}"; do
            [ -n "$rk" ] || continue
            AWS_ACCESS_KEY_ID="$OFF_AK" AWS_SECRET_ACCESS_KEY="$OFF_SK" AWS_DEFAULT_REGION="$OFF_REGION" \
                aws s3 rm "$OFF_DEST/$rk" "${ep[@]}" --only-show-errors && echo "Off-box: pruned remote $rk"
        done
    else
        echo "ERROR: off-box upload FAILED. The local backup is fine but is NOT disaster-safe." >&2
        echo "       Check R2/S3 credentials + network, then re-run. See scripts/RECOVERY.md." >&2
        exit 3
    fi
fi
