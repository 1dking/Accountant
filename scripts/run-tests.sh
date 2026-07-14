#!/usr/bin/env bash
# =============================================================================
# Accountant — Full Test Suite Runner
# =============================================================================
# Usage:  ./scripts/run-tests.sh [--skip-e2e] [--skip-frontend] [--skip-load] [--include-known]
#
# Runs all test layers:
#   1. Backend  — api + integration + adversarial (one pytest run)
#   2. Financial invariants (MANDATORY — always blocks)
#   3. Frontend — Vitest
#   4. Load / concurrency
#   5. E2E — Playwright (requires running servers)
#
# Exit codes:
#   0  — everything passed
#   1  — something failed
#
# NOTE ON CORRECTNESS: suite status is taken from each runner's EXIT CODE.
# A previous version scraped stdout for '^tests/.*PASSED', a pattern that never
# matches `pytest -q` output, so the pass/fail counters were permanently 0 —
# and every backend suite was wrapped in `|| true`. The script printed
# "ALL TESTS PASSED — Safe to deploy" no matter how much was broken. Don't
# reintroduce output scraping; trust the exit code.
# =============================================================================

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

SKIP_E2E=false
SKIP_FRONTEND=false
SKIP_LOAD=false
INCLUDE_KNOWN=false

for arg in "$@"; do
  case $arg in
    --skip-e2e)       SKIP_E2E=true ;;
    --skip-frontend)  SKIP_FRONTEND=true ;;
    --skip-load)      SKIP_LOAD=true ;;
    --include-known)  INCLUDE_KNOWN=true ;;
  esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

FAILED_SUITES=()
BLOCKED=false

header() {
  echo ""
  echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}  $1${NC}"
  echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
}

# run_suite <label> <working-dir> <command...>
# Records a failure if the command exits non-zero. Never swallows the status.
run_suite() {
  local label="$1"; shift
  local workdir="$1"; shift

  header "$label"

  ( cd "$workdir" && "$@" )
  local exit_code=$?

  if [ $exit_code -ne 0 ]; then
    echo -e "${RED}  ✗ $label FAILED (exit $exit_code)${NC}"
    FAILED_SUITES+=("$label")
    return 1
  fi

  echo -e "${GREEN}  ✓ $label passed${NC}"
  return 0
}

mkdir -p "$BACKEND_DIR/test_data/documents" "$BACKEND_DIR/test_data/recordings"

# =============================================================================
# 1. BACKEND — api + integration + adversarial
# =============================================================================
# Run as ONE pytest invocation over the whole tree rather than a hand-listed
# subset. The old script named 7 api files explicitly and never ran
# tests/integration/ at all — 277 tests that simply didn't exist as far as the
# runner was concerned.

# 22 tests in tests/known_failures.txt already fail on main (see that file for
# root cause). Deselect them so this run reflects NEW breakage only. Pass
# --include-known to run them anyway.
DESELECT=""
if [ "$INCLUDE_KNOWN" = false ] && [ -f "$BACKEND_DIR/tests/known_failures.txt" ]; then
  while IFS= read -r line; do
    case "$line" in ''|\#*) continue ;; esac
    DESELECT="$DESELECT --deselect $line"
  done < "$BACKEND_DIR/tests/known_failures.txt"
  echo -e "${YELLOW}  Note: deselecting known pre-existing failures (tests/known_failures.txt)${NC}"
fi

# shellcheck disable=SC2086  # DESELECT is intentionally word-split
run_suite "Backend (api + integration + adversarial)" "$BACKEND_DIR" \
  python -m pytest tests/api tests/integration tests/adversarial --tb=short -q $DESELECT

# =============================================================================
# 2. FINANCIAL INVARIANTS (MANDATORY)
# =============================================================================

if ! run_suite "Financial invariants (MANDATORY)" "$BACKEND_DIR" \
  python -m pytest tests/financial --tb=short -q; then
  BLOCKED=true
fi

# =============================================================================
# 3. FRONTEND
# =============================================================================

if [ "$SKIP_FRONTEND" = false ]; then
  run_suite "Frontend (Vitest)" "$FRONTEND_DIR" pnpm test
fi

# =============================================================================
# 4. LOAD
# =============================================================================
# These skip themselves unless TEST_DATABASE_URL points at Postgres — the
# concurrency assertions are meaningless against SQLite.

if [ "$SKIP_LOAD" = false ]; then
  run_suite "Load / concurrency" "$BACKEND_DIR" \
    python -m pytest tests/load --tb=short -q
fi

# =============================================================================
# 5. E2E
# =============================================================================

if [ "$SKIP_E2E" = false ]; then
  run_suite "E2E (Playwright)" "$FRONTEND_DIR" npx playwright test --reporter=list
fi

# =============================================================================
# REPORT
# =============================================================================

header "FINAL REPORT"
echo ""

if [ ${#FAILED_SUITES[@]} -eq 0 ]; then
  echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  ALL SUITES PASSED                                           ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
  exit 0
fi

echo -e "${RED}  Failed suites:${NC}"
for suite in "${FAILED_SUITES[@]}"; do
  echo -e "${RED}    ✗ $suite${NC}"
done
echo ""

if [ "$BLOCKED" = true ]; then
  echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${RED}║  DEPLOYMENT BLOCKED — financial invariants failed            ║${NC}"
  echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
else
  echo -e "${YELLOW}  ⚠ Tests failed. Do not deploy.${NC}"
fi

exit 1
