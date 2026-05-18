#!/usr/bin/env bash
# Smoke test runner: executes the integration test suite that covers
# the 6 bug-pattern regressions (see backend/tests/integration/).
#
# Designed for pre-commit / pre-deploy use. Exits non-zero on any
# failure so it can gate commits.
#
# Usage:
#   ./scripts/smoke-test.sh
#
# Bypass (use sparingly, e.g. during emergency hotfix when tests
# can't be updated in time):
#   SKIP_SMOKE=1 ./scripts/smoke-test.sh

set -euo pipefail

if [[ "${SKIP_SMOKE:-0}" == "1" ]]; then
    echo "SKIP_SMOKE=1 — smoke tests bypassed"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/backend"

# Ensure venv is active or use direct .venv path
if [[ -z "${VIRTUAL_ENV:-}" ]] && [[ -d ".venv" ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

echo "Running integration smoke tests (6 bug-pattern regressions)…"
python -m pytest tests/integration/ -v --tb=short -q
status=$?

if [[ $status -ne 0 ]]; then
    echo ""
    echo "Smoke tests FAILED. Don't commit/deploy until these pass."
    echo "To bypass in emergency: SKIP_SMOKE=1 git commit ..."
    exit $status
fi

echo ""
echo "All integration smoke tests passed."

# ---------------------------------------------------------------------------
# Stale-bundle check
# ---------------------------------------------------------------------------
# Catches the "pnpm build silently failed → dist/ never regenerated → scp
# pushed an old bundle" footgun that bit the email-absorption ship on
# 2026-05-18. If frontend source has been edited since the last successful
# build, warn loudly so the deployer rebuilds before scp'ing.
#
# Heuristic: compare mtime of dist/index.html to the newest source file
# under frontend/src. If any source is newer than the bundle, the bundle
# is stale.

FRONTEND_DIST="$REPO_ROOT/frontend/dist/index.html"
FRONTEND_SRC="$REPO_ROOT/frontend/src"

if [[ -f "$FRONTEND_DIST" ]] && [[ -d "$FRONTEND_SRC" ]]; then
    newest_src=$(find "$FRONTEND_SRC" -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.css" \) -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1)
    if [[ -n "$newest_src" ]]; then
        src_epoch=${newest_src%% *}
        src_epoch=${src_epoch%.*}
        dist_epoch=$(stat -c '%Y' "$FRONTEND_DIST" 2>/dev/null || stat -f '%m' "$FRONTEND_DIST" 2>/dev/null)
        if [[ -n "$dist_epoch" ]] && (( src_epoch > dist_epoch )); then
            echo ""
            echo "⚠  WARNING: frontend/dist/ is older than frontend/src/."
            echo "   Source file: ${newest_src#* }"
            echo "   Run 'cd frontend && pnpm build' before deploying or you'll"
            echo "   push a stale bundle. Capture build output too:"
            echo "     pnpm build 2>&1 | tee /tmp/build.log"
            echo "     grep -E 'ELIFECYCLE|error TS' /tmp/build.log && exit 1"
        fi
    fi
fi
