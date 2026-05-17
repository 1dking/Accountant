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
