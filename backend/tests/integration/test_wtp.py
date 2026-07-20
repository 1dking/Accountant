"""WTP interview CSV ingest — parsing, the monotonic-order check (mirrors
OBrain_WTP_Capture.xlsx's own AB-column formula exactly), and the
operator-only gate (reusing require_platform_admin, tested directly at the
function level for the same reason app/events' router tests do — booting the
full app crashes this Windows dev machine via an unrelated python-magic/
libmagic DLL issue; see tests/integration/test_events.py's note).
"""
import csv
from pathlib import Path

import pytest

from app.wtp.service import WTP_CSV_PATH, parse_wtp_csv

HEADERS = [
    "respondent_id", "orgId", "segment", "industry", "team_size", "current_tier",
    "interview_date", "interviewer", "Q1 replaced_tools", "Q1 old_stack_$/mo",
    "Q2 first_thing_breaks", "Q3 daily_module", "Q3 surprise_module",
    "Q4 too_expensive_$", "Q5 expensive_$", "Q6 bargain_$", "Q7 too_cheap_$",
    "Q8 metric_pref", "Q8 why", "Q9 gmv_fairness", "Q10 react_$49",
    "Q10 react_$179", "Q11 unlock_$179", "Q12 agency_wtp_$", "Q12 resell_$",
    "Close fair_increase", "notes", "VW_order_check",
]


def _row(**overrides) -> dict:
    base = {h: "" for h in HEADERS}
    base.update({
        "respondent_id": "R01", "orgId": "org_test1", "segment": "Team",
        "Q4 too_expensive_$": "199", "Q5 expensive_$": "149",
        "Q6 bargain_$": "89", "Q7 too_cheap_$": "29",
        "Q8 metric_pref": "Clients", "Q9 gmv_fairness": "Fair",
        "Q10 react_$49": "fair", "Q10 react_$179": "worth it",
    })
    base.update(overrides)
    return base


def _write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "interviews.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


class TestParseWtpCsv:
    def test_valid_row_parses(self, tmp_path):
        p = _write_csv(tmp_path, [_row()])
        rows = parse_wtp_csv(p)
        assert len(rows) == 1
        r = rows[0]
        assert r["orgId"] == "org_test1"
        assert r["tooExpensive"] == 199.0
        assert r["expensive"] == 149.0
        assert r["bargain"] == 89.0
        assert r["tooCheap"] == 29.0
        assert r["metricPref"] == "Clients"
        assert r["gmvFairness"] == "Fair"
        assert r["react49"] == "fair"

    def test_missing_file_returns_empty(self, tmp_path):
        assert parse_wtp_csv(tmp_path / "does_not_exist.csv") == []

    def test_empty_csv_header_only_returns_empty(self, tmp_path):
        p = _write_csv(tmp_path, [])
        assert parse_wtp_csv(p) == []

    def test_non_monotonic_row_is_skipped(self, tmp_path):
        # bargain (89) > expensive (69) — violates too_cheap<bargain<expensive<too_expensive
        bad = _row(orgId="org_bad", **{"Q5 expensive_$": "69"})
        good = _row(orgId="org_good")
        rows = parse_wtp_csv(_write_csv(tmp_path, [bad, good]))
        assert [r["orgId"] for r in rows] == ["org_good"]

    def test_equal_values_fail_strict_monotonic(self, tmp_path):
        # too_cheap == bargain — the sheet's check is strict (<), not (<=)
        tied = _row(orgId="org_tied", **{"Q7 too_cheap_$": "89"})
        rows = parse_wtp_csv(_write_csv(tmp_path, [tied]))
        assert rows == []

    def test_missing_price_is_skipped(self, tmp_path):
        incomplete = _row(orgId="org_incomplete", **{"Q6 bargain_$": ""})
        rows = parse_wtp_csv(_write_csv(tmp_path, [incomplete]))
        assert rows == []

    def test_blank_org_id_is_skipped(self, tmp_path):
        rows = parse_wtp_csv(_write_csv(tmp_path, [_row(orgId="")]))
        assert rows == []

    def test_unrecognized_metric_pref_falls_back_to_other(self, tmp_path):
        row = _row(orgId="org_x", **{"Q8 metric_pref": "Seats"})
        rows = parse_wtp_csv(_write_csv(tmp_path, [row]))
        assert rows[0]["metricPref"] == "Other"

    def test_multiple_valid_rows(self, tmp_path):
        rows_in = [_row(orgId=f"org_{i}", **{"Q6 bargain_$": str(80 + i)}) for i in range(5)]
        rows = parse_wtp_csv(_write_csv(tmp_path, rows_in))
        assert len(rows) == 5
        assert {r["orgId"] for r in rows} == {f"org_{i}" for i in range(5)}

    def test_real_shipped_csv_is_the_honest_empty_template(self):
        """The actual local file (exported from the real OBrain_WTP_Capture.xlsx;
        backend/data/ is gitignored like the rest of that directory, so this is a
        manually-placed operator artifact, not something git ships) has zero real
        respondents right now — the workbook's only populated row is its own
        styled example, which the export step excludes. This is not a bug; it's
        the true state until real interviews are conducted."""
        assert WTP_CSV_PATH.exists(), "wtp_interviews.csv should exist locally at backend/data/"
        rows = parse_wtp_csv(WTP_CSV_PATH)
        assert rows == []


class TestWtpRouterGate:
    async def test_admin_allowed(self, admin_user):
        from tests.conftest import TEST_SETTINGS
        from app.platform_admin.router import require_platform_admin

        class _FakeApp:
            def __init__(self, settings):
                from types import SimpleNamespace
                self.state = SimpleNamespace(settings=settings)

        class _FakeRequest:
            def __init__(self, settings):
                self.app = _FakeApp(settings)

        result = await require_platform_admin(_FakeRequest(TEST_SETTINGS), admin_user)
        assert result is admin_user

    async def test_non_admin_forbidden(self, team_member_user):
        from fastapi import HTTPException
        from tests.conftest import TEST_SETTINGS
        from app.platform_admin.router import require_platform_admin

        class _FakeApp:
            def __init__(self, settings):
                from types import SimpleNamespace
                self.state = SimpleNamespace(settings=settings)

        class _FakeRequest:
            def __init__(self, settings):
                self.app = _FakeApp(settings)

        with pytest.raises(HTTPException) as exc_info:
            await require_platform_admin(_FakeRequest(TEST_SETTINGS), team_member_user)
        assert exc_info.value.status_code == 403

    async def test_endpoint_function_returns_wrapped_data(self, admin_user):
        from app.wtp.router import wtp_responses
        result = await wtp_responses(admin_user)
        assert "data" in result
        assert isinstance(result["data"], list)
