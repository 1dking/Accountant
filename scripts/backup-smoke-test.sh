#!/usr/bin/env bash
# backup-smoke-test.sh — Prove the backup is actually restorable.
#
# A backup you haven't restored is not a backup. This seeds a throwaway SQLite
# DB + a canary file, runs backup.sh, restores the archive into a sandbox, and
# asserts the row + file survived the round-trip. Exits non-zero on any mismatch.
# Runs fully in temp dirs — touches nothing real. CI-safe (Linux).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

export DB_PATH="$SANDBOX/src/accountant.db"
export DOCS_DIR="$SANDBOX/src/documents"
export BACKUP_DEST="$SANDBOX/backups"
export KEEP=3
# Keep the round-trip test hermetic: no off-box upload. /dev/null is not a
# regular file, so backup.sh's R2 fallback reads nothing and stays local-only.
export ENV_FILE=/dev/null
unset BACKUP_S3_DEST

mkdir -p "$SANDBOX/src/documents"

# Seed a DB with a known row.
python3 - "$DB_PATH" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.execute("CREATE TABLE t (id INTEGER, v TEXT)")
c.execute("INSERT INTO t VALUES (1, 'hello-backup')")
c.commit(); c.close()
PY

# Seed a canary file.
echo "canary-file-contents" > "$SANDBOX/src/documents/canary.txt"

# 1. Back up.
bash "$SCRIPT_DIR/backup.sh"

ARCHIVE="$(ls -1t "$BACKUP_DEST"/accountant-*.tar.gz 2>/dev/null | head -1 || true)"
[ -n "$ARCHIVE" ] || { echo "FAIL: no archive produced"; exit 1; }

# 2. Restore into a sandbox.
REST="$SANDBOX/restored"
bash "$SCRIPT_DIR/restore.sh" "$ARCHIVE" "$REST"

# 3. Verify the DB row.
V="$(python3 - "$REST/accountant.db" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
print(c.execute("SELECT v FROM t WHERE id=1").fetchone()[0])
c.close()
PY
)"
[ "$V" = "hello-backup" ] || { echo "FAIL: DB value mismatch (got '$V')"; exit 1; }

# 4. Verify the canary file.
grep -q "canary-file-contents" "$REST/documents/canary.txt" \
    || { echo "FAIL: restored canary file mismatch"; exit 1; }

echo "SMOKE TEST PASSED: backup + restore round-trip verified"
