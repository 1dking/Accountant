"""2026 Canadian payroll deduction parameters — CRA T4127 123rd edition
(effective 2026-07-01) plus CPP/EI/QPP/QPIP annual figures.

This file is DATA. When January comes: copy to tables_2027.py, update the
numbers from the new T4127, bump ``calc.T`` to point at it. Nothing in
calc.py should need to change for a rate change.

Sources (2026-09-06):
  T4127 122nd (Jan 2026) https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/t4127-payroll-deductions-formulas/t4127-jan/t4127-jan-payroll-deductions-formulas-computer-programs.html
  T4127 123rd (Jul 2026) https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/t4127-payroll-deductions-formulas/t4127-jul/t4127-jul-payroll-deductions-formulas.html
  CPP https://www.canada.ca/en/services/benefits/publicpensions/cpp/contributions.html
  EI  https://www.canada.ca/en/employment-social-development/news/2025/09/canada-employment-insurance-commission-sets-the-2026-employment-insurance-premium-rate.html
  QPP https://www.retraitequebec.gouv.qc.ca/en/programs/quebec-pension-plan/work-contributions
  QPIP https://www.rqap.gouv.qc.ca/en/news/reduction-in-premium-rates-for-the-quebec-parental-insurance-plan-in-2026
  QC  https://cdn-contenu.quebec.ca/cdn-contenu/adm/min/finances/publications-adm/parametres/AUTEN_IncomeTax2026.pdf

Mid-year note: the 123rd edition changed BC (lowest rate + reduction), NL
(BPA to 15,000 prorated) and PE (new top bracket). Those are the Jul–Dec
values below; Jan–Jun values are in the comments for reference.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import NamedTuple

VERSION = "2026-07"  # T4127 123rd edition

#: Federal tax abatement for Quebec employment (T4127 Ch. 7) — Quebec collects
#: its own income tax, so the federal amount is reduced by this fraction.
QC_FEDERAL_ABATEMENT = "0.165"


class Bracket(NamedTuple):
    threshold: str   # lower bound of the bracket, annual $
    rate: str        # marginal rate as a decimal string, e.g. "0.14"


# ---------------------------------------------------------------------------
# Pension plans
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PensionPlan:
    ympe: str
    yampe: str
    basic_exemption: str
    employee_rate: str        # total first-tier rate (base + enhancement)
    base_rate: str            # the pre-2019 base component — the ONLY part that is a tax credit (K2)
    employee_rate_2: str      # second-tier (CPP2/QPP2) rate on YMPE..YAMPE
    max_employee: str         # annual max first-tier contribution
    max_employee_2: str       # annual max second-tier contribution

    @property
    def enhancement_rate(self) -> Decimal:
        """The post-2019 enhancement — deductible from income (F5), not a credit."""
        return Decimal(self.employee_rate) - Decimal(self.base_rate)

    @property
    def max_employee_base(self) -> Decimal:
        """Max annual base-component contribution — the K2 cap."""
        return (Decimal(self.max_employee) * Decimal(self.base_rate) / Decimal(self.employee_rate)).quantize(Decimal("0.01"))


CPP = PensionPlan(
    ympe="74600", yampe="85000", basic_exemption="3500",
    employee_rate="0.0595", base_rate="0.0495", employee_rate_2="0.04",
    max_employee="4230.45", max_employee_2="416.00",
)

QPP = PensionPlan(
    ympe="74600", yampe="85000", basic_exemption="3500",
    employee_rate="0.0630", base_rate="0.0530", employee_rate_2="0.04",
    max_employee="4479.30", max_employee_2="416.00",
)


# ---------------------------------------------------------------------------
# EI / QPIP
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EIPlan:
    mie: str
    employee_rate: str
    employee_rate_qc: str
    employer_multiplier: str
    max_employee: str
    max_employee_qc: str


EI = EIPlan(
    mie="68900",
    employee_rate="0.0163", employee_rate_qc="0.0130",
    employer_multiplier="1.4",
    max_employee="1123.07", max_employee_qc="895.70",
)


@dataclass(frozen=True)
class QPIPPlan:
    mie: str
    employee_rate: str
    employer_rate: str
    max_employee: str
    max_employer: str


QPIP = QPIPPlan(mie="103000", employee_rate="0.00430", employer_rate="0.00602",
                max_employee="442.90", max_employer="620.06")


# ---------------------------------------------------------------------------
# Federal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Federal:
    brackets: list[Bracket]
    bpa_max: str
    bpa_min: str
    bpa_phase_start: str
    bpa_phase_end: str
    canada_employment_amount: str
    indexation: str


FEDERAL = Federal(
    brackets=[
        Bracket("0", "0.14"),
        Bracket("58523", "0.205"),
        Bracket("117045", "0.26"),
        Bracket("181440", "0.29"),
        Bracket("258482", "0.33"),
    ],
    bpa_max="16452", bpa_min="14829",
    bpa_phase_start="181440", bpa_phase_end="258482",
    canada_employment_amount="1501",
    indexation="0.020",
)


# ---------------------------------------------------------------------------
# Provinces
# ---------------------------------------------------------------------------

Adjust = Callable[[Decimal, Decimal], Decimal]   # (basic_prov_tax, annual_income) -> adjusted
BPAFn = Callable[[Decimal], Decimal]             # (annual_income) -> BPA


@dataclass(frozen=True)
class Province:
    code: str
    brackets: list[Bracket]
    #: Basic personal amount — a fixed number, or a function of annual income
    #: (MB phases out; YT mirrors the federal enhanced BPA).
    bpa: str | BPAFn
    #: Applied in order to (basic tax, A): surtaxes, premiums, reductions.
    adjustments: list[Adjust] = field(default_factory=list)
    #: Provincial employment amount (Yukon mirrors the federal CEA as K4P).
    employment_amount: str | None = None
    #: Where the provincial tax is remitted. Only QC differs.
    remit_to: str = "CRA"


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


# --- Ontario: surtax (V1) + health premium (V2) + tax reduction (S) ---
def _on_surtax(t4: Decimal, _a: Decimal) -> Decimal:
    if t4 <= Decimal("5818"):
        v1 = Decimal("0")
    elif t4 <= Decimal("7446"):
        v1 = Decimal("0.20") * (t4 - Decimal("5818"))
    else:
        v1 = Decimal("0.20") * (t4 - Decimal("5818")) + Decimal("0.36") * (t4 - Decimal("7446"))
    return t4 + v1


def _on_reduction(t4_plus_v1: Decimal, _a: Decimal) -> Decimal:
    # S = min(T4+V1, 2×(300+Y) − (T4+V1)); Y = dependants (not modelled → 0).
    base_red = Decimal("300")
    s = min(t4_plus_v1, Decimal("2") * base_red - t4_plus_v1)
    return t4_plus_v1 - max(Decimal("0"), s)


def _on_health_premium(t: Decimal, a: Decimal) -> Decimal:
    if a <= Decimal("20000"):
        v2 = Decimal("0")
    elif a <= Decimal("36000"):
        v2 = min(Decimal("300"), Decimal("0.06") * (a - Decimal("20000")))
    elif a <= Decimal("48000"):
        v2 = min(Decimal("450"), Decimal("300") + Decimal("0.06") * (a - Decimal("36000")))
    elif a <= Decimal("72000"):
        v2 = min(Decimal("600"), Decimal("450") + Decimal("0.25") * (a - Decimal("48000")))
    elif a <= Decimal("200000"):
        v2 = min(Decimal("750"), Decimal("600") + Decimal("0.25") * (a - Decimal("72000")))
    else:
        v2 = min(Decimal("900"), Decimal("750") + Decimal("0.25") * (a - Decimal("200000")))
    return t + v2


# --- BC: tax reduction (S) — Jul–Dec 2026 values ---
def _bc_reduction(t4: Decimal, a: Decimal) -> Decimal:
    if a <= Decimal("25570"):
        s = min(t4, Decimal("805"))
    elif a <= Decimal("44952"):
        s = min(t4, Decimal("805") - (a - Decimal("25570")) * Decimal("0.0356"))
    else:
        s = Decimal("0")
    return t4 - max(Decimal("0"), s)


# --- MB: BPA phases from 15,780 to 0 between NI 200k and 400k ---
def _mb_bpa(a: Decimal) -> Decimal:
    full = Decimal("15780")
    if a <= Decimal("200000"):
        return full
    if a >= Decimal("400000"):
        return Decimal("0")
    return _q(full * (Decimal("400000") - a) / Decimal("200000"))


# --- YT: BPA mirrors the federal enhanced BPA ---
def _yt_bpa(a: Decimal) -> Decimal:
    f = FEDERAL
    if a <= Decimal(f.bpa_phase_start):
        return Decimal(f.bpa_max)
    if a >= Decimal(f.bpa_phase_end):
        return Decimal(f.bpa_min)
    span = Decimal(f.bpa_phase_end) - Decimal(f.bpa_phase_start)
    return _q(Decimal(f.bpa_max) - (Decimal(f.bpa_max) - Decimal(f.bpa_min)) * (a - Decimal(f.bpa_phase_start)) / span)


PROVINCES: dict[str, Province] = {
    "ON": Province("ON", [
        Bracket("0", "0.0505"), Bracket("53891", "0.0915"), Bracket("107785", "0.1116"),
        Bracket("150000", "0.1216"), Bracket("220000", "0.1316"),
    ], bpa="12989", adjustments=[_on_surtax, _on_reduction, _on_health_premium]),

    # Jul–Dec 2026 (123rd ed.). Jan–Jun: lowest 0.0506, reduction 575/41722.
    "BC": Province("BC", [
        Bracket("0", "0.0614"), Bracket("50363", "0.077"), Bracket("100728", "0.105"),
        Bracket("115648", "0.1229"), Bracket("140430", "0.147"), Bracket("190405", "0.168"),
        Bracket("265545", "0.205"),
    ], bpa="13216", adjustments=[_bc_reduction]),

    "AB": Province("AB", [
        Bracket("0", "0.08"), Bracket("61200", "0.10"), Bracket("154259", "0.12"),
        Bracket("185111", "0.13"), Bracket("246813", "0.14"), Bracket("370220", "0.15"),
    ], bpa="22769"),

    # Quebec: computed here for the stub/net; remitted to Revenu Québec (TP-1015.F).
    "QC": Province("QC", [
        Bracket("0", "0.14"), Bracket("54345", "0.19"), Bracket("108680", "0.24"), Bracket("132245", "0.2575"),
    ], bpa="18952", remit_to="RQ"),

    "SK": Province("SK", [
        Bracket("0", "0.105"), Bracket("54532", "0.125"), Bracket("155805", "0.145"),
    ], bpa="20381"),

    "MB": Province("MB", [
        Bracket("0", "0.108"), Bracket("47000", "0.1275"), Bracket("100000", "0.174"),
    ], bpa=_mb_bpa),

    # NS: BPA formula removed for 2026 — flat.
    "NS": Province("NS", [
        Bracket("0", "0.0879"), Bracket("30995", "0.1495"), Bracket("61991", "0.1667"),
        Bracket("97417", "0.175"), Bracket("157124", "0.21"),
    ], bpa="11932"),

    "NB": Province("NB", [
        Bracket("0", "0.094"), Bracket("52333", "0.14"), Bracket("104666", "0.16"), Bracket("193861", "0.195"),
    ], bpa="13664"),

    # NL Jul–Dec: BPA 15,000 (Jan–Jun 11,188; full-year 13,094).
    "NL": Province("NL", [
        Bracket("0", "0.087"), Bracket("44678", "0.145"), Bracket("89354", "0.158"),
        Bracket("159528", "0.178"), Bracket("223340", "0.198"), Bracket("285319", "0.208"),
        Bracket("570638", "0.213"), Bracket("1141275", "0.218"),
    ], bpa="15000"),

    # PE Jul–Dec adds a 21% bracket at 200,000.
    "PE": Province("PE", [
        Bracket("0", "0.095"), Bracket("33928", "0.1347"), Bracket("65820", "0.166"),
        Bracket("106890", "0.1762"), Bracket("142520", "0.19"), Bracket("200000", "0.21"),
    ], bpa="15000"),

    "YT": Province("YT", [
        Bracket("0", "0.064"), Bracket("58523", "0.09"), Bracket("117045", "0.109"),
        Bracket("181440", "0.128"), Bracket("500000", "0.15"),
    ], bpa=_yt_bpa, employment_amount="1501"),

    "NT": Province("NT", [
        Bracket("0", "0.059"), Bracket("53003", "0.086"), Bracket("106009", "0.122"), Bracket("172346", "0.1405"),
    ], bpa="18198"),

    "NU": Province("NU", [
        Bracket("0", "0.04"), Bracket("55801", "0.07"), Bracket("111602", "0.09"), Bracket("181439", "0.115"),
    ], bpa="19659"),
}


# ---------------------------------------------------------------------------
# Vacation pay minimums (Employment Standards) — % of gross, by years of service.
# (threshold_years, pct) ascending. Verify against each ESA before relying on
# it for compliance; used only as the default when adding an employee.
# ---------------------------------------------------------------------------

VACATION_MINIMUMS: dict[str, list[tuple[int, str]]] = {
    "ON": [(0, "4"), (5, "6")],
    "BC": [(0, "4"), (5, "6")],
    "AB": [(0, "4"), (5, "6")],
    "MB": [(0, "4"), (5, "6")],
    "SK": [(0, "5.77"), (10, "7.69")],   # 3/52 → 4/52
    "QC": [(0, "4"), (3, "6")],
    "NB": [(0, "4"), (8, "6")],
    "NS": [(0, "4"), (8, "6")],
    "PE": [(0, "4"), (8, "6")],
    "NL": [(0, "4"), (15, "6")],
    "YT": [(0, "4")],
    "NT": [(0, "4"), (5, "6")],
    "NU": [(0, "4"), (5, "6")],
}


def vacation_pct(province: str, years_of_service: int) -> Decimal:
    steps = VACATION_MINIMUMS.get(province.upper(), [(0, "4")])
    pct = steps[0][1]
    for years, p in steps:
        if years_of_service >= years:
            pct = p
    return Decimal(pct)
