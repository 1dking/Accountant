"""The payroll deduction engine — CRA T4127 "Option 1" (tax-on-annualised-income).

Pure functions. No DB, no I/O. Every statutory number comes from
:mod:`tables_2026` so a January rate change is a table edit, not a code edit.
Money is Decimal, rounded half-up to the cent the way CRA's formulas specify.

Per-period flow for one employee (``compute_period``):

  1. Gross for the period (regular + OT + bonus + vacation + other).
  2. CPP / CPP2 (or QPP in Quebec) — contribution on pensionable earnings above
     the per-period basic exemption, capped by the YTD maximum.
  3. EI (or EI-reduced + QPIP in Quebec) — on insurable earnings, capped by the
     YTD maximum.
  4. Federal tax — annualise (A = P × taxable-per-period), apply brackets,
     subtract non-refundable credits (BPA via TD1, CPP, EI, Canada Employment
     Amount), divide by P.
  5. Provincial tax — same shape with the province's table; ON adds surtax +
     health premium; BC applies its tax reduction; QC is computed but remitted
     separately (Revenu Québec).
  6. Net = gross − (CPP + CPP2 + EI + QPIP + fed + prov + other).

Employer cost = CPP (1×) + CPP2 (1×) + EI (1.4×) + QPIP (employer rate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from . import tables_2026 as T

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def q(v) -> Decimal:
    """Round half-up to the cent (CRA convention)."""
    return (v if isinstance(v, Decimal) else Decimal(str(v))).quantize(CENT, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------


@dataclass
class YTD:
    """Year-to-date totals BEFORE this period, used for annual caps."""
    pensionable_earnings: Decimal = ZERO
    cpp_employee: Decimal = ZERO
    cpp2_employee: Decimal = ZERO
    insurable_earnings: Decimal = ZERO
    ei_employee: Decimal = ZERO
    qpip_employee: Decimal = ZERO


@dataclass
class PeriodInput:
    province: str                      # province of employment (ISO-3166-2:CA)
    pay_periods: int                   # P — 52 / 26 / 24 / 12
    regular_pay: Decimal = ZERO
    overtime_pay: Decimal = ZERO
    bonus: Decimal = ZERO
    vacation_pay: Decimal = ZERO
    other_earnings: Decimal = ZERO
    other_deductions: Decimal = ZERO   # non-statutory (benefits, garnishment)
    td1_federal_claim: Decimal | None = None      # TC — None = basic personal amount
    td1_provincial_claim: Decimal | None = None   # TCP — None = provincial BPA
    additional_tax: Decimal = ZERO     # TD1 "additional tax to be deducted" per period
    cpp_exempt: bool = False
    ei_exempt: bool = False
    ytd: YTD = field(default_factory=YTD)


@dataclass
class PeriodResult:
    gross: Decimal
    pensionable_earnings: Decimal
    insurable_earnings: Decimal
    cpp_employee: Decimal
    cpp2_employee: Decimal
    cpp_employer: Decimal
    cpp2_employer: Decimal
    ei_employee: Decimal
    ei_employer: Decimal
    qpip_employee: Decimal
    qpip_employer: Decimal
    federal_tax: Decimal
    provincial_tax: Decimal
    other_deductions: Decimal
    net_pay: Decimal
    #: Annualised taxable income used for the tax computation (audit aid).
    annual_taxable_income: Decimal
    tables_version: str = T.VERSION


# ---------------------------------------------------------------------------
# CPP / QPP
# ---------------------------------------------------------------------------


def compute_cpp(gross: Decimal, P: int, ytd: YTD, *, province: str, exempt: bool) -> tuple[Decimal, Decimal]:
    """(base contribution, CPP2 contribution) for the employee this period.

    Base: rate × (pensionable − exemption/P), capped so YTD never exceeds the
    annual maximum. CPP2: second-rate on earnings between YMPE and YAMPE, again
    YTD-capped. Quebec uses QPP with its own rate but the same shape.
    """
    if exempt or gross <= 0:
        return ZERO, ZERO

    plan = T.QPP if province == "QC" else T.CPP
    exemption_per_period = q(Decimal(plan.basic_exemption) / P)

    # --- Base contribution up to YMPE ---
    room_ympe = max(ZERO, Decimal(plan.ympe) - ytd.pensionable_earnings)
    pensionable_this = min(gross, room_ympe)
    contributory = max(ZERO, pensionable_this - exemption_per_period)
    base = q(contributory * Decimal(plan.employee_rate))
    base_room = max(ZERO, Decimal(plan.max_employee) - ytd.cpp_employee)
    base = min(base, base_room)

    # --- CPP2 between YMPE and YAMPE ---
    ytd_after = ytd.pensionable_earnings + gross
    over_ympe_start = max(ytd.pensionable_earnings, Decimal(plan.ympe))
    over_ympe_end = min(ytd_after, Decimal(plan.yampe))
    cpp2_base = max(ZERO, over_ympe_end - over_ympe_start)
    cpp2 = q(cpp2_base * Decimal(plan.employee_rate_2))
    cpp2_room = max(ZERO, Decimal(plan.max_employee_2) - ytd.cpp2_employee)
    cpp2 = min(cpp2, cpp2_room)

    return base, cpp2


# ---------------------------------------------------------------------------
# EI / QPIP
# ---------------------------------------------------------------------------


def compute_ei(gross: Decimal, ytd: YTD, *, province: str, exempt: bool) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """(ei_employee, ei_employer, qpip_employee, qpip_employer).

    Insurable earnings are capped at MIE. Quebec pays a reduced EI rate plus
    QPIP; everywhere else pays full EI and no QPIP. Employer EI = 1.4 × employee.
    """
    if exempt or gross <= 0:
        return ZERO, ZERO, ZERO, ZERO

    room_mie = max(ZERO, Decimal(T.EI.mie) - ytd.insurable_earnings)
    insurable = min(gross, room_mie)

    rate = Decimal(T.EI.employee_rate_qc if province == "QC" else T.EI.employee_rate)
    max_emp = Decimal(T.EI.max_employee_qc if province == "QC" else T.EI.max_employee)
    ei = q(insurable * rate)
    ei = min(ei, max(ZERO, max_emp - ytd.ei_employee))
    ei_er = q(ei * Decimal(T.EI.employer_multiplier))

    qpip = qpip_er = ZERO
    if province == "QC":
        room_qpip = max(ZERO, Decimal(T.QPIP.mie) - ytd.insurable_earnings)
        qpip_base = min(gross, room_qpip)
        qpip = q(qpip_base * Decimal(T.QPIP.employee_rate))
        qpip = min(qpip, max(ZERO, Decimal(T.QPIP.max_employee) - ytd.qpip_employee))
        qpip_er = q(qpip_base * Decimal(T.QPIP.employer_rate))

    return ei, ei_er, qpip, qpip_er


# ---------------------------------------------------------------------------
# Income tax — T4127 Option 1
# ---------------------------------------------------------------------------


def _tax_on(annual: Decimal, brackets: list[T.Bracket]) -> Decimal:
    """Progressive tax on an annual amount. Brackets are (threshold, rate) with
    threshold = lower bound; the last bracket runs to infinity."""
    if annual <= 0:
        return ZERO
    tax = Decimal("0")
    for i, b in enumerate(brackets):
        lower = Decimal(b.threshold)
        upper = Decimal(brackets[i + 1].threshold) if i + 1 < len(brackets) else None
        if annual <= lower:
            break
        taxable_here = (min(annual, upper) if upper is not None else annual) - lower
        tax += taxable_here * Decimal(b.rate)
    return tax


def _federal_bpa(annual_income: Decimal) -> Decimal:
    """Enhanced basic personal amount — phases from max to min across the
    fourth bracket. T4127 Chapter 6 formula."""
    f = T.FEDERAL
    if annual_income <= Decimal(f.bpa_phase_start):
        return Decimal(f.bpa_max)
    if annual_income >= Decimal(f.bpa_phase_end):
        return Decimal(f.bpa_min)
    span = Decimal(f.bpa_phase_end) - Decimal(f.bpa_phase_start)
    drop = (Decimal(f.bpa_max) - Decimal(f.bpa_min)) * (annual_income - Decimal(f.bpa_phase_start)) / span
    return Decimal(f.bpa_max) - drop


@dataclass
class _Credits:
    """Annualised statutory amounts that feed the K2 credit, per T4127 §6.

    Only the BASE component of CPP/QPP (4.95% / 5.30%) is a credit; the 2019+
    enhancement and CPP2 are an income DEDUCTION (F5) applied before brackets.
    """
    cpp_base: Decimal     # min(P × period_cpp × base/total, max_employee_base)
    ei: Decimal           # min(P × period_ei, max_employee)
    qpip: Decimal         # min(P × period_qpip, max_employee) — QC only


def compute_federal_tax(
    *, annual_taxable: Decimal, P: int, td1_claim: Decimal | None, credits: _Credits,
    province: str = "ON",
) -> Decimal:
    """T3 — federal tax per period.

    T3 = ( T(A) − K1 − K2 − K4 ) / P, floored at 0, where
      T(A) = bracket tax on annual income A (A already net of the F5 deduction)
      K1   = lowest rate × TC   (TD1 total claim; default = enhanced BPA)
      K2   = lowest rate × (base CPP + EI [+ QPIP]), each capped
      K4   = lowest rate × Canada Employment Amount (capped at A)
    """
    f = T.FEDERAL
    A = annual_taxable
    if A <= 0:
        return ZERO
    lowest = Decimal(f.brackets[0].rate)
    TC = Decimal(td1_claim) if td1_claim is not None else _federal_bpa(A)

    tax = _tax_on(A, f.brackets)
    K1 = lowest * TC
    K2 = lowest * (credits.cpp_base + credits.ei + credits.qpip)
    K4 = lowest * min(A, Decimal(f.canada_employment_amount))
    annual_tax = max(ZERO, tax - K1 - K2 - K4)
    # Quebec abatement — T4127 Chapter 7: federal tax for QC employment is
    # reduced by 16.5% because Quebec collects its own income tax directly.
    if province == "QC":
        annual_tax = annual_tax * (Decimal("1") - Decimal(T.QC_FEDERAL_ABATEMENT))
    return q(annual_tax / P)


def compute_provincial_tax(
    *, province: str, annual_taxable: Decimal, P: int, td1_claim: Decimal | None, credits: _Credits,
) -> Decimal:
    """T4 — provincial tax per period. Same shape as federal, plus province-
    specific layers (ON surtax + health premium + reduction, BC reduction,
    YT employment amount). BPA may be a function of income (MB, YT).
    """
    p = T.PROVINCES.get(province)
    if p is None or annual_taxable <= 0:
        return ZERO
    A = annual_taxable
    lowest = Decimal(p.brackets[0].rate)
    if td1_claim is not None:
        TCP = Decimal(td1_claim)
    else:
        TCP = p.bpa(A) if callable(p.bpa) else Decimal(p.bpa)

    tax = _tax_on(A, p.brackets)
    K1P = lowest * TCP
    K2P = lowest * (credits.cpp_base + credits.ei + credits.qpip)
    K4P = lowest * min(A, Decimal(p.employment_amount)) if p.employment_amount else ZERO
    basic = max(ZERO, tax - K1P - K2P - K4P)

    # Province-specific adjustments, each a pure function of (basic, A).
    for adj in p.adjustments:
        basic = adj(basic, A)

    return q(max(ZERO, basic) / P)


# ---------------------------------------------------------------------------
# Whole period
# ---------------------------------------------------------------------------


def compute_period(inp: PeriodInput) -> PeriodResult:
    P = inp.pay_periods
    gross = q(inp.regular_pay + inp.overtime_pay + inp.bonus + inp.vacation_pay + inp.other_earnings)

    cpp, cpp2 = compute_cpp(gross, P, inp.ytd, province=inp.province, exempt=inp.cpp_exempt)
    ei, ei_er, qpip, qpip_er = compute_ei(gross, inp.ytd, province=inp.province, exempt=inp.ei_exempt)

    plan = T.QPP if inp.province == "QC" else T.CPP

    # F5 — the enhanced-CPP deduction: the post-2019 enhancement share of the
    # first-tier contribution, plus all of CPP2. Deducted from income before
    # brackets (it is NOT a credit).
    f5 = ZERO
    if cpp or cpp2:
        enh_share = plan.enhancement_rate / Decimal(plan.employee_rate)
        f5 = cpp * enh_share + cpp2

    # Annualise. T4127: A = P × (I − F − F2 − U1 − F5). F/F2/U1 (registered
    # plans, support, union dues) are not modelled — 0.
    A = (gross - f5) * P

    # K2 inputs — annualised and capped. Only the BASE CPP component counts.
    base_share = Decimal(plan.base_rate) / Decimal(plan.employee_rate)
    credits = _Credits(
        cpp_base=min(cpp * base_share * P, plan.max_employee_base),
        ei=min(ei * P, Decimal(T.EI.max_employee_qc if inp.province == "QC" else T.EI.max_employee)),
        qpip=min(qpip * P, Decimal(T.QPIP.max_employee)) if inp.province == "QC" else ZERO,
    )

    fed = compute_federal_tax(
        annual_taxable=A, P=P, td1_claim=inp.td1_federal_claim, credits=credits, province=inp.province,
    )
    prov = compute_provincial_tax(
        province=inp.province, annual_taxable=A, P=P, td1_claim=inp.td1_provincial_claim, credits=credits,
    )
    fed = q(fed + inp.additional_tax)

    deductions = cpp + cpp2 + ei + qpip + fed + prov + q(inp.other_deductions)
    net = q(gross - deductions)

    pensionable = min(gross, max(ZERO, Decimal(plan.yampe) - inp.ytd.pensionable_earnings))
    insurable = min(gross, max(ZERO, Decimal(T.EI.mie) - inp.ytd.insurable_earnings))

    return PeriodResult(
        gross=gross,
        pensionable_earnings=q(pensionable),
        insurable_earnings=q(insurable),
        cpp_employee=cpp, cpp2_employee=cpp2,
        cpp_employer=cpp, cpp2_employer=cpp2,          # employer matches 1:1
        ei_employee=ei, ei_employer=ei_er,
        qpip_employee=qpip, qpip_employer=qpip_er,
        federal_tax=fed, provincial_tax=prov,
        other_deductions=q(inp.other_deductions),
        net_pay=net,
        annual_taxable_income=q(A),
    )
