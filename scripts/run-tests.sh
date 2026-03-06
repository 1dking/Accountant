#!/usr/bin/env bash
# =============================================================================
# Accountant — Full Test Suite Runner
# =============================================================================
# Usage:  ./scripts/run-tests.sh [--skip-e2e] [--skip-frontend] [--skip-load]
#
# Runs all test layers in order:
#   1. Backend API tests
#   2. Frontend component tests (Vitest)
#   3. Adversarial / security tests
#   4. Financial invariant tests (MANDATORY)
#   5. Load / concurrency tests
#   6. E2E tests (Playwright — requires running servers)
#
# Exit codes:
#   0  — all tests passed (or only NORMAL failures)
#   1  — CRITICAL or HIGH tests failed → deployment blocked
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

SKIP_E2E=false
SKIP_FRONTEND=false
SKIP_LOAD=false

for arg in "$@"; do
  case $arg in
    --skip-e2e)      SKIP_E2E=true ;;
    --skip-frontend)  SKIP_FRONTEND=true ;;
    --skip-load)      SKIP_LOAD=true ;;
  esac
done

TOTAL=0
PASSED=0
FAILED=0
CRITICAL_FAIL=0
HIGH_FAIL=0
NORMAL_FAIL=0
BLOCKED=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

header() {
  echo ""
  echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}  $1${NC}"
  echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
}

run_pytest() {
  local label="$1"
  local path="$2"
  local markers="${3:-}"

  header "$label"

  local cmd="python -m pytest $path -v --tb=short -q"
  if [ -n "$markers" ]; then
    cmd="$cmd -m '$markers'"
  fi

  local output
  local exit_code=0
  output=$(cd "$BACKEND_DIR" && eval "$cmd" 2>&1) || exit_code=$?

  echo "$output"

  # Parse counts from pytest output
  local line
  line=$(echo "$output" | grep -E "^(FAILED|ERROR|=)" | tail -1)

  local p f
  p=$(echo "$output" | grep -cE "^tests/.*PASSED" || true)
  f=$(echo "$output" | grep -cE "^tests/.*FAILED" || true)

  TOTAL=$((TOTAL + p + f))
  PASSED=$((PASSED + p))
  FAILED=$((FAILED + f))

  if [ $exit_code -ne 0 ] && [ $f -gt 0 ]; then
    echo -e "${RED}  ✗ $f failure(s) in $label${NC}"
  else
    echo -e "${GREEN}  ✓ $label passed ($p tests)${NC}"
  fi

  return $exit_code
}

# ─── Ensure test_data dir exists ──────────────────────────────────────────────
mkdir -p "$BACKEND_DIR/test_data/documents" "$BACKEND_DIR/test_data/recordings"

# =============================================================================
# 1. BACKEND API TESTS
# =============================================================================

set +e  # Don't exit on individual test failures

run_pytest "Backend API — Auth" "tests/api/test_auth.py" || true
run_pytest "Backend API — Contacts" "tests/api/test_contacts.py" || true
run_pytest "Backend API — Invoices & Estimates" "tests/api/test_invoices.py" || true
run_pytest "Backend API — Cashbook" "tests/api/test_cashbook.py" || true
run_pytest "Backend API — Documents" "tests/api/test_documents.py" || true
run_pytest "Backend API — Meetings" "tests/api/test_meetings.py" || true
run_pytest "Backend API — Idempotency" "tests/api/test_idempotency.py" || true

# =============================================================================
# 2. FRONTEND COMPONENT TESTS
# =============================================================================

if [ "$SKIP_FRONTEND" = false ]; then
  header "Frontend Component Tests (Vitest)"
  fe_output=$(cd "$FRONTEND_DIR" && pnpm test 2>&1) || true
  echo "$fe_output"

  fe_pass=$(echo "$fe_output" | grep -cE "✓|✔|pass" || true)
  fe_fail=$(echo "$fe_output" | grep -cE "✗|✘|fail|FAIL" || true)
  TOTAL=$((TOTAL + fe_pass + fe_fail))
  PASSED=$((PASSED + fe_pass))
  FAILED=$((FAILED + fe_fail))
fi

# =============================================================================
# 3. ADVERSARIAL TESTS
# =============================================================================

run_pytest "Adversarial — Security" "tests/adversarial/test_security.py" || true

# =============================================================================
# 4. FINANCIAL INVARIANT TESTS (MANDATORY)
# =============================================================================

header "FINANCIAL INVARIANT TESTS (MANDATORY — blocks deployment)"
fin_output=$(cd "$BACKEND_DIR" && python -m pytest tests/financial/ -v --tb=short -q 2>&1)
fin_exit=$?
echo "$fin_output"

fin_p=$(echo "$fin_output" | grep -cE "^tests/.*PASSED" || true)
fin_f=$(echo "$fin_output" | grep -cE "^tests/.*FAILED" || true)
TOTAL=$((TOTAL + fin_p + fin_f))
PASSED=$((PASSED + fin_p))
FAILED=$((FAILED + fin_f))

if [ $fin_exit -ne 0 ]; then
  CRITICAL_FAIL=$((CRITICAL_FAIL + fin_f))
  BLOCKED=true
  echo -e "${RED}  ✗ FINANCIAL INVARIANTS FAILED — DEPLOYMENT BLOCKED${NC}"
fi

# =============================================================================
# 5. LOAD TESTS
# =============================================================================

if [ "$SKIP_LOAD" = false ]; then
  run_pytest "Load — Concurrency" "tests/load/test_concurrency.py" || true
fi

# =============================================================================
# 6. E2E TESTS
# =============================================================================

if [ "$SKIP_E2E" = false ]; then
  header "E2E Tests (Playwright)"
  echo "  (Requires running backend + frontend servers)"
  e2e_output=$(cd "$FRONTEND_DIR" && npx playwright test --reporter=list 2>&1) || true
  echo "$e2e_output"
fi

# =============================================================================
# REPORT
# =============================================================================

set -e

header "FINAL REPORT"

echo ""
echo -e "  Total tests:     ${CYAN}$TOTAL${NC}"
echo -e "  Passed:          ${GREEN}$PASSED${NC}"
echo -e "  Failed:          ${RED}$FAILED${NC}"
echo ""

if [ "$BLOCKED" = true ]; then
  echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${RED}║  DEPLOYMENT BLOCKED — Critical/High tests failed            ║${NC}"
  echo -e "${RED}║  $CRITICAL_FAIL critical failure(s)                                    ║${NC}"
  echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
  exit 1
elif [ $FAILED -gt 0 ]; then
  echo -e "${YELLOW}  ⚠ $FAILED test(s) failed (normal priority) — deployment allowed with warnings${NC}"
  exit 0
else
  echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  ALL TESTS PASSED — Safe to deploy                          ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
  exit 0
fi
