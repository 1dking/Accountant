#!/usr/bin/env bash
# restore.sh — Restore a backup produced by backup.sh.
#
# Two modes:
#   1. SANDBOX (safe, default when a target dir is given):
#        bash restore.sh <archive.tar.gz> /tmp/restore-check
#      Extracts the DB + files into the target dir. Touches nothing live.
#      Used by backup-smoke-test.sh to prove backups are restorable.
#
#   2. IN-PLACE (dangerous — overwrites the live DB + files):
#        bash stop.sh                       # stop the app first
#        CONFIRM=yes bash restore.sh <archive.tar.gz>
#      Requires CONFIRM=yes so it can't fire by accident.
#
# Config (in-place targets, overridable via env):
#   DB_PATH   default backend/data/accountant.db
#   DOCS_DIR  default backend/data/documents
set -euo pipefail

ARCHIVE="${1:?usage: restore.sh <archive.tar.gz> [sandbox_target_dir]}"
TARGET="${2:-}"

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${DB_PATH:-$APP_DIR/backend/data/accountant.db}"
DOCS_DIR="${DOCS_DIR:-$APP_DIR/backend/data/documents}"

[ -f "$ARCHIVE" ] || { echo "Archive not found: $ARCHIVE"; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
tar -xzf "$ARCHIVE" -C "$WORK"

if [ -n "$TARGET" ]; then
    # --- SANDBOX restore -------------------------------------------------
    mkdir -p "$TARGET"
    [ -f "$WORK/accountant.db" ] && cp "$WORK/accountant.db" "$TARGET/accountant.db"
    [ -f "$WORK/documents.tar.gz" ] && tar -xzf "$WORK/documents.tar.gz" -C "$TARGET"
    echo "Restored into sandbox: $TARGET"
    exit 0
fi

# --- IN-PLACE restore ----------------------------------------------------
if [ "${CONFIRM:-}" != "yes" ]; then
    echo "Refusing in-place restore without CONFIRM=yes."
    echo "Stop the app (bash stop.sh), then: CONFIRM=yes bash restore.sh $ARCHIVE"
    exit 1
fi

mkdir -p "$(dirname "$DB_PATH")"
if [ -f "$WORK/accountant.db" ]; then
    cp "$WORK/accountant.db" "$DB_PATH"
    echo "Restored DB -> $DB_PATH"
fi
if [ -f "$WORK/documents.tar.gz" ]; then
    rm -rf "$DOCS_DIR"
    mkdir -p "$(dirname "$DOCS_DIR")"
    tar -xzf "$WORK/documents.tar.gz" -C "$(dirname "$DOCS_DIR")"
    echo "Restored files -> $DOCS_DIR"
fi
echo "In-place restore complete. Start the app: bash start.sh"
