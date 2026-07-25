#!/usr/bin/env bash
# backup.sh — Snapshot the production SQLite DB + uploaded files.
#
# Produces a single timestamped tarball in $BACKUP_DEST containing:
#   - accountant.db      (consistent online snapshot via SQLite .backup)
#   - documents.tar.gz   (the uploaded-files directory)
#   - manifest.txt       (what/when)
# and prunes all but the newest $KEEP archives.
#
# Config (all overridable via env):
#   DB_PATH      path to the live SQLite DB   (default backend/data/accountant.db)
#   DOCS_DIR     uploaded files directory     (default backend/data/documents)
#   BACKUP_DEST  where archives are written   (default <repo>/backups)
#   KEEP         how many archives to retain  (default 14)
#
# Restore with restore.sh. See scripts/BACKUPS.md for scheduling + restore steps.
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

# 5. Retention: keep only the newest $KEEP archives.
mapfile -t OLD < <(ls -1t "$BACKUP_DEST"/accountant-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))")
for old in "${OLD[@]:-}"; do
    [ -n "$old" ] || continue
    rm -f "$old"
    echo "Pruned old backup: $old"
done
