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
# Stale-bundle gate
# ---------------------------------------------------------------------------
# Catches the "pnpm build silently failed → dist/ never regenerated → scp
# pushed an old bundle" footgun that bit the email-absorption ship on
# 2026-05-18. Two checks:
#
#   1. FAIL if frontend/dist/index.html is older than HEAD's commit
#      timestamp. That means you committed without rebuilding (or your
#      `pnpm build` died and you didn't notice).
#   2. WARN if any frontend/src/*.ts(x)/css is newer than dist (catches
#      local edits in flight; doesn't fail because local-dev iteration
#      legitimately churns source faster than rebuilds).
#
# Bypass: SKIP_BUNDLE_CHECK=1 prefixed to the smoke-test invocation,
# documented in the failure message.

FRONTEND_DIST="$REPO_ROOT/frontend/dist/index.html"
FRONTEND_SRC="$REPO_ROOT/frontend/src"

if [[ -f "$FRONTEND_DIST" ]] && [[ -d "$FRONTEND_SRC" ]] && [[ "${SKIP_BUNDLE_CHECK:-0}" != "1" ]]; then
    dist_epoch=$(stat -c '%Y' "$FRONTEND_DIST" 2>/dev/null || stat -f '%m' "$FRONTEND_DIST" 2>/dev/null)

    # Find the most-recent commit that touched frontend/ — backend-only
    # commits shouldn't trigger a stale-bundle fail since they don't
    # require a rebuild.
    head_epoch=$(git -C "$REPO_ROOT" log -1 --format=%ct -- frontend/ 2>/dev/null)

    # Gate 1: hard fail if dist is older than the latest frontend-touching commit.
    if [[ -n "$head_epoch" ]] && [[ -n "$dist_epoch" ]] && (( head_epoch > dist_epoch )); then
        echo ""
        echo "❌  STALE BUNDLE — frontend/dist/index.html is older than HEAD commit."
        echo ""
        echo "    HEAD commit: $(date -d @"$head_epoch" 2>/dev/null || date -r "$head_epoch")"
        echo "    dist/index.html: $(date -d @"$dist_epoch" 2>/dev/null || date -r "$dist_epoch")"
        echo ""
        echo "    Run a fresh build before deploying:"
        echo "      cd frontend && pnpm build 2>&1 | tee /tmp/build.log"
        echo "      grep -E 'ELIFECYCLE|error TS' /tmp/build.log && exit 1"
        echo ""
        echo "    Bypass (NOT recommended): SKIP_BUNDLE_CHECK=1 $0"
        exit 1
    fi

    # Gate 2: warn (don't fail) if uncommitted source edits are newer than dist.
    newest_src=$(find "$FRONTEND_SRC" -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.css" \) -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1)
    if [[ -n "$newest_src" ]]; then
        src_epoch=${newest_src%% *}
        src_epoch=${src_epoch%.*}
        if [[ -n "$dist_epoch" ]] && (( src_epoch > dist_epoch )); then
            echo ""
            echo "⚠  WARNING: frontend/src/ has edits newer than dist/."
            echo "   Newest source: ${newest_src#* }"
            echo "   Run 'cd frontend && pnpm build' before deploying."
        fi
    fi
fi
