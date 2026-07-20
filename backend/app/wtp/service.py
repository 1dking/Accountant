"""Willingness-to-pay interview ingest — a manually-curated research cohort,
not live product telemetry. The operator conducts interviews, fills in
OBrain_WTP_Capture.xlsx (Interviews tab), exports it to CSV, and drops it at
WTP_CSV_PATH. This module reads that CSV fresh on every request — it's a
handful of rows at most (n=10-15 per the workbook's own honesty note), so
there's no case for caching or persisting it into the app's own database.

Column layout and the monotonic-order check mirror the workbook's Interviews
sheet exactly (see its AB column formula: `=IF(COUNT(N,O,P,Q)<4,"",IF(AND(
Q<P,P<O,O<N),"ok","CHECK ORDER"))`) so a row that fails order in the sheet
also fails here — the "too cheap < bargain < expensive < too expensive"
check is not this module's invention.
"""
import csv
from pathlib import Path
from typing import Any

WTP_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "wtp_interviews.csv"

# Real header strings from OBrain_WTP_Capture.xlsx's Interviews tab, row 3.
_ORG_ID = "orgId"
_SEGMENT = "segment"
_TOO_EXPENSIVE = "Q4 too_expensive_$"
_EXPENSIVE = "Q5 expensive_$"
_BARGAIN = "Q6 bargain_$"
_TOO_CHEAP = "Q7 too_cheap_$"
_METRIC_PREF = "Q8 metric_pref"
_GMV_FAIRNESS = "Q9 gmv_fairness"
_REACT_49 = "Q10 react_$49"
_REACT_179 = "Q10 react_$179"
_RESPONDENT_ID = "respondent_id"

VALID_METRIC_PREFS = {"Clients", "GMV", "Other"}


def _to_float(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_wtp_csv(path: Path | str = WTP_CSV_PATH) -> list[dict[str, Any]]:
    """Returns one dict per valid respondent. Rows are skipped (not errored)
    when: the row is blank, any of the four VW prices is missing/unparseable,
    or the monotonic check fails — a bad interview shouldn't 500 the endpoint
    for every other one that's fine.
    """
    p = Path(path)
    if not p.exists():
        return []

    out: list[dict[str, Any]] = []
    with open(p, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            org_id = (row.get(_ORG_ID) or "").strip()
            if not org_id:
                continue

            too_expensive = _to_float(row.get(_TOO_EXPENSIVE))
            expensive = _to_float(row.get(_EXPENSIVE))
            bargain = _to_float(row.get(_BARGAIN))
            too_cheap = _to_float(row.get(_TOO_CHEAP))
            if None in (too_expensive, expensive, bargain, too_cheap):
                continue

            # Exact mirror of the sheet's AB-column monotonic check.
            if not (too_cheap < bargain < expensive < too_expensive):
                continue

            metric_pref = (row.get(_METRIC_PREF) or "").strip()
            if metric_pref not in VALID_METRIC_PREFS:
                metric_pref = "Other"

            out.append({
                "respondentId": (row.get(_RESPONDENT_ID) or "").strip() or None,
                "orgId": org_id,
                "segment": (row.get(_SEGMENT) or "").strip() or None,
                "tooExpensive": too_expensive,
                "expensive": expensive,
                "bargain": bargain,
                "tooCheap": too_cheap,
                "metricPref": metric_pref,
                "gmvFairness": (row.get(_GMV_FAIRNESS) or "").strip() or None,
                "react49": (row.get(_REACT_49) or "").strip() or None,
                "react179": (row.get(_REACT_179) or "").strip() or None,
            })
    return out


def get_wtp_responses() -> list[dict[str, Any]]:
    return parse_wtp_csv()
