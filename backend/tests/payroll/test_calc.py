"""Pure-function tests for the T4127 engine. No DB.

Reference values were hand-checked against the CRA formulas and cross-checked
against published 2026 payroll calculators on 2026-09-06. If a January table
update changes a number here, that's expected — update the fixture with the
new T4127 edition, don't loosen the assertion.
"""
from decimal import Decimal as D

import pytest

from app.payroll import calc
from app.payroll import tables_2026 as T


def _period(province, P, regular, vacation=D("0"), **kw):
    return calc.compute_period(calc.PeriodInput(
        province=province, pay_periods=P, regular_pay=D(str(regular)), vacation_pay=D(str(vacation)),
        ytd=kw.pop("ytd", calc.YTD()), **kw,
    ))


def test_cpp_base_formula_ontario():
    r = _period("ON", 26, "2307.69", "92.31")  # $60k + 4%
    assert r.gross == D("2400.00")
    # (2400 − 3500/26) × 5.95%
    assert r.cpp_employee == D("134.79")
    assert r.cpp_employer == r.cpp_employee
    assert r.cpp2_employee == D("0.00")


def test_ei_and_employer_multiplier():
    r = _period("ON", 26, "2400")
    assert r.ei_employee == D("39.12")            # 2400 × 1.63%
    assert r.ei_employer == D("54.77")            # × 1.4


def test_ontario_income_tax_plausible():
    r = _period("ON", 26, "2307.69", "92.31")
    # ~$5.8k federal, ~$3.2k Ontario per year on ~$62k — within a few dollars
    # of published calculators; exact to the cent under our F5/K2 treatment.
    assert r.federal_tax == D("223.20")
    assert r.provincial_tax == D("122.76")
    assert r.net_pay == D("1880.13")


def test_quebec_uses_qpp_qpip_reduced_ei_and_abatement():
    r = _period("QC", 26, "2307.69", "92.31")
    assert r.cpp_employee == D("142.72")          # QPP 6.30%
    assert r.ei_employee == D("31.20")            # 1.30%
    assert r.qpip_employee == D("10.32")          # 0.43%
    assert r.qpip_employer == D("14.45")          # 0.602%
    # Federal tax is abated 16.5% for Quebec employment.
    on = _period("ON", 26, "2307.69", "92.31")
    assert r.federal_tax < on.federal_tax * D("0.86")


def test_ytd_caps_stop_cpp_and_ei_but_not_cpp2():
    ytd = calc.YTD(
        pensionable_earnings=D(T.CPP.ympe), cpp_employee=D(T.CPP.max_employee),
        insurable_earnings=D(T.EI.mie), ei_employee=D(T.EI.max_employee),
    )
    r = _period("ON", 26, "3000", ytd=ytd)
    assert r.cpp_employee == D("0.00")
    assert r.ei_employee == D("0.00")
    assert r.cpp2_employee == D("120.00")         # 4% × 3000, between YMPE and YAMPE


def test_cpp2_caps_at_yampe():
    ytd = calc.YTD(pensionable_earnings=D("84000"), cpp_employee=D(T.CPP.max_employee))
    r = _period("AB", 12, "5000", ytd=ytd)
    # Only 1000 of room left below YAMPE 85000 → CPP2 = 40.00
    assert r.cpp2_employee == D("40.00")


def test_below_bpa_pays_no_income_tax():
    r = _period("ON", 26, "300")
    assert r.federal_tax == D("0.00")
    assert r.provincial_tax == D("0.00")
    assert r.cpp_employee == D("9.84")            # still contributes


def test_exemptions():
    r = _period("BC", 26, "2000", cpp_exempt=True, ei_exempt=True)
    assert r.cpp_employee == r.ei_employee == D("0.00")
    assert r.net_pay == r.gross - r.federal_tax - r.provincial_tax


def test_additional_tax_and_other_deductions_flow_to_net():
    base = _period("ON", 26, "2000")
    extra = _period("ON", 26, "2000", additional_tax=D("50"), other_deductions=D("25"))
    assert extra.federal_tax == base.federal_tax + D("50")
    assert extra.net_pay == base.net_pay - D("75")


def test_ontario_health_premium_kicks_in_above_20k():
    lo = _period("ON", 12, "1600")     # ~19.2k/yr → no premium
    hi = _period("ON", 12, "2000")     # 24k/yr → premium applies
    # Provincial tax at 24k should exceed a pure bracket scale-up of 19.2k
    assert hi.provincial_tax > lo.provincial_tax * D("1.25")


@pytest.mark.parametrize("province", list(T.PROVINCES))
def test_every_province_computes(province):
    r = _period(province, 26, "2500")
    assert r.gross == D("2500.00")
    assert r.net_pay > D("0")
    assert r.net_pay < r.gross


def test_tables_version_stamped():
    assert _period("ON", 26, "1000").tables_version == T.VERSION


def test_vacation_minimum_lookup():
    assert T.vacation_pct("ON", 0) == D("4")
    assert T.vacation_pct("ON", 5) == D("6")
    assert T.vacation_pct("QC", 3) == D("6")
    assert T.vacation_pct("SK", 0) == D("5.77")
