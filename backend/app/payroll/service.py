"""Payroll service — employees, runs, approval (journal posting), remittance.

Tenancy: every query goes through ``apply_cashbook_filter`` on (user_id,
org_id), the same scope as the chart of accounts, so a payroll run can only
ever post to its own tenant's ledger.

Lifecycle of a run
------------------
  create  → DRAFT    stubs computed from employee defaults + overrides
  recalc  → DRAFT    inputs changed; every stub recomputed (YTD re-read)
  approve → APPROVED journal posted atomically; stubs' YTD frozen
  mark_paid → PAID   second journal: Dr Wages Payable / Cr Bank
  void    → VOID     reversing journal for whatever was posted

YTD is derived, not stored on the employee: it is the sum of stubs on
APPROVED/PAID runs whose pay_date falls in the same calendar year. That keeps
a void from leaving a stale counter behind.
"""
from __future__ import annotations

import logging
import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.accounting import coa_service
from app.accounting.journal_service import post_journal
from app.accounting.ledger_models import ChartAccount
from app.auth.models import User
from app.core.authorization import apply_cashbook_filter
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.payroll import calc
from app.payroll.models import (
    PAY_PERIODS,
    Employee,
    EmployeeStatus,
    PayFrequency,
    PayrollRun,
    PayrollRunStatus,
    PayStub,
    PayType,
)
from app.payroll.schemas import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeYTD,
    PayrollRunCreate,
    PreviewRequest,
    PreviewResponse,
    RemittanceSummary,
    StubOverride,
)

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
_ACTIVE_RUN_STATUSES = (PayrollRunStatus.APPROVED, PayrollRunStatus.PAID)


def _org_id_for(user: User) -> uuid.UUID | None:
    if user.cashbook_access == "org" and user.org_id:
        return user.org_id
    return None


def _q(v) -> Decimal:
    return calc.q(v)


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------


async def list_employees(db: AsyncSession, user: User, *, include_terminated: bool = False) -> list[Employee]:
    stmt = select(Employee)
    stmt = apply_cashbook_filter(stmt, Employee.user_id, Employee.org_id, user)
    if not include_terminated:
        stmt = stmt.where(Employee.status != EmployeeStatus.TERMINATED)
    stmt = stmt.order_by(Employee.last_name, Employee.first_name)
    return list((await db.execute(stmt)).scalars().all())


async def get_employee(db: AsyncSession, user: User, employee_id: uuid.UUID) -> Employee:
    stmt = select(Employee).where(Employee.id == employee_id)
    stmt = apply_cashbook_filter(stmt, Employee.user_id, Employee.org_id, user)
    emp = (await db.execute(stmt)).scalar_one_or_none()
    if emp is None:
        raise NotFoundError("Employee", str(employee_id))
    return emp


async def create_employee(db: AsyncSession, user: User, data: EmployeeCreate) -> Employee:
    from app.accounting import canadian_tax

    if data.province_of_employment not in canadian_tax.PROVINCES:
        raise ValidationError(f"Unknown province of employment: {data.province_of_employment}")
    emp = Employee(user_id=user.id, org_id=_org_id_for(user), **data.model_dump())
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


async def update_employee(db: AsyncSession, user: User, employee_id: uuid.UUID, data: EmployeeUpdate) -> Employee:
    emp = await get_employee(db, user, employee_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(emp, k, v)
    if emp.termination_date and emp.status == EmployeeStatus.ACTIVE:
        emp.status = EmployeeStatus.TERMINATED
    await db.commit()
    await db.refresh(emp)
    return emp


async def delete_employee(db: AsyncSession, user: User, employee_id: uuid.UUID) -> None:
    """Hard delete only if no stubs exist; otherwise terminate."""
    emp = await get_employee(db, user, employee_id)
    has_stubs = (await db.execute(
        select(func.count(PayStub.id)).where(PayStub.employee_id == emp.id)
    )).scalar_one()
    if has_stubs:
        emp.status = EmployeeStatus.TERMINATED
        emp.termination_date = emp.termination_date or date.today()
    else:
        await db.delete(emp)
    await db.commit()


# ---------------------------------------------------------------------------
# YTD
# ---------------------------------------------------------------------------


async def employee_ytd(
    db: AsyncSession, user: User, employee_id: uuid.UUID, *, year: int, before_run_id: uuid.UUID | None = None
) -> EmployeeYTD:
    """Sum of this employee's stubs on APPROVED/PAID runs with pay_date in ``year``.
    ``before_run_id`` excludes that run (used while computing it)."""
    cols = (
        func.coalesce(func.sum(PayStub.gross), 0),
        func.coalesce(func.sum(PayStub.cpp_employee), 0),
        func.coalesce(func.sum(PayStub.cpp2_employee), 0),
        func.coalesce(func.sum(PayStub.ei_employee), 0),
        func.coalesce(func.sum(PayStub.qpip_employee), 0),
        func.coalesce(func.sum(PayStub.federal_tax), 0),
        func.coalesce(func.sum(PayStub.provincial_tax), 0),
        func.coalesce(func.sum(PayStub.insurable_earnings), 0),
        func.coalesce(func.sum(PayStub.insurable_hours), 0),
        func.coalesce(func.sum(PayStub.pensionable_earnings), 0),
        func.coalesce(func.sum(PayStub.net_pay), 0),
        func.count(PayStub.id),
    )
    stmt = (
        select(*cols)
        .join(PayrollRun, PayrollRun.id == PayStub.run_id)
        .where(
            PayStub.employee_id == employee_id,
            PayrollRun.status.in_(_ACTIVE_RUN_STATUSES),
            PayrollRun.pay_date >= date(year, 1, 1),
            PayrollRun.pay_date <= date(year, 12, 31),
        )
    )
    if before_run_id is not None:
        stmt = stmt.where(PayrollRun.id != before_run_id)
    stmt = apply_cashbook_filter(stmt, PayrollRun.user_id, PayrollRun.org_id, user)
    row = (await db.execute(stmt)).one()
    return EmployeeYTD(
        employee_id=employee_id, year=year,
        gross=_q(row[0]), cpp_employee=_q(row[1]), cpp2_employee=_q(row[2]), ei_employee=_q(row[3]),
        qpip_employee=_q(row[4]), federal_tax=_q(row[5]), provincial_tax=_q(row[6]),
        insurable_earnings=_q(row[7]), insurable_hours=_q(row[8]), pensionable_earnings=_q(row[9]),
        net=_q(row[10]), stub_count=int(row[11] or 0),
    )


# ---------------------------------------------------------------------------
# Computing a stub
# ---------------------------------------------------------------------------


@dataclass
class _StubInputs:
    hours: Decimal | None
    regular_pay: Decimal
    overtime_pay: Decimal
    bonus: Decimal
    vacation_pay: Decimal
    vacation_accrual: Decimal   # not paid — accrues to the liability
    other_earnings: Decimal
    other_deductions: Decimal
    notes: str | None


def _period_inputs(emp: Employee, freq: PayFrequency, ov: StubOverride | None) -> _StubInputs:
    P = PAY_PERIODS[freq]
    if emp.pay_type == PayType.HOURLY:
        hours = ov.hours if (ov and ov.hours is not None) else (emp.default_hours_per_period or ZERO)
        regular = _q(Decimal(hours) * Decimal(emp.pay_rate))
    else:
        hours = ov.hours if ov else None
        regular = _q(Decimal(emp.pay_rate) / P)

    pct = Decimal(emp.vacation_pay_pct) / Decimal("100")
    earned_vac = _q(regular * pct)
    payout = _q(ov.vacation_payout) if ov else ZERO
    if emp.vacation_pay_each_period:
        vacation_pay, accrual = earned_vac + payout, ZERO
    else:
        vacation_pay, accrual = payout, earned_vac

    return _StubInputs(
        hours=Decimal(hours) if hours is not None else None,
        regular_pay=regular,
        overtime_pay=_q(ov.overtime_pay) if ov else ZERO,
        bonus=_q(ov.bonus) if ov else ZERO,
        vacation_pay=vacation_pay,
        vacation_accrual=accrual,
        other_earnings=_q(ov.other_earnings) if ov else ZERO,
        other_deductions=_q(ov.other_deductions) if ov else ZERO,
        notes=ov.notes if ov else None,
    )


async def _compute_stub(
    db: AsyncSession, user: User, run: PayrollRun, emp: Employee, ov: StubOverride | None, existing: PayStub | None
) -> PayStub:
    P = PAY_PERIODS[run.pay_frequency]
    inputs = _period_inputs(emp, run.pay_frequency, ov)
    ytd_before = await employee_ytd(db, user, emp.id, year=run.pay_date.year, before_run_id=run.id)

    res = calc.compute_period(calc.PeriodInput(
        province=emp.province_of_employment,
        pay_periods=P,
        regular_pay=inputs.regular_pay,
        overtime_pay=inputs.overtime_pay,
        bonus=inputs.bonus,
        vacation_pay=inputs.vacation_pay,
        other_earnings=inputs.other_earnings,
        other_deductions=inputs.other_deductions,
        td1_federal_claim=emp.td1_federal_claim,
        td1_provincial_claim=emp.td1_provincial_claim,
        additional_tax=Decimal(emp.additional_tax_per_period or 0),
        cpp_exempt=emp.cpp_exempt or _cpp_age_exempt(emp, run.pay_date),
        ei_exempt=emp.ei_exempt,
        ytd=calc.YTD(
            pensionable_earnings=ytd_before.pensionable_earnings,
            cpp_employee=ytd_before.cpp_employee,
            cpp2_employee=ytd_before.cpp2_employee,
            insurable_earnings=ytd_before.insurable_earnings,
            ei_employee=ytd_before.ei_employee,
            qpip_employee=ytd_before.qpip_employee,
        ),
    ))

    stub = existing or PayStub(run_id=run.id, employee_id=emp.id)
    stub.hours = inputs.hours
    stub.rate = emp.pay_rate
    stub.regular_pay = inputs.regular_pay
    stub.overtime_pay = inputs.overtime_pay
    stub.bonus = inputs.bonus
    stub.vacation_pay = inputs.vacation_pay
    stub.other_earnings = inputs.other_earnings
    stub.gross = res.gross
    stub.cpp_employee, stub.cpp2_employee = res.cpp_employee, res.cpp2_employee
    stub.ei_employee, stub.qpip_employee = res.ei_employee, res.qpip_employee
    stub.federal_tax, stub.provincial_tax = res.federal_tax, res.provincial_tax
    stub.other_deductions, stub.net_pay = res.other_deductions, res.net_pay
    stub.cpp_employer, stub.cpp2_employer = res.cpp_employer, res.cpp2_employer
    stub.ei_employer, stub.qpip_employer = res.ei_employer, res.qpip_employer
    stub.insurable_earnings, stub.pensionable_earnings = res.insurable_earnings, res.pensionable_earnings
    stub.insurable_hours = inputs.hours if inputs.hours is not None else _q(Decimal("2080") / P)
    # YTD AFTER this stub
    stub.ytd_gross = _q(ytd_before.gross + res.gross)
    stub.ytd_cpp_employee = _q(ytd_before.cpp_employee + res.cpp_employee)
    stub.ytd_cpp2_employee = _q(ytd_before.cpp2_employee + res.cpp2_employee)
    stub.ytd_ei_employee = _q(ytd_before.ei_employee + res.ei_employee)
    stub.ytd_qpip_employee = _q(ytd_before.qpip_employee + res.qpip_employee)
    stub.ytd_federal_tax = _q(ytd_before.federal_tax + res.federal_tax)
    stub.ytd_provincial_tax = _q(ytd_before.provincial_tax + res.provincial_tax)
    stub.ytd_insurable_earnings = _q(ytd_before.insurable_earnings + res.insurable_earnings)
    stub.ytd_pensionable_earnings = _q(ytd_before.pensionable_earnings + res.pensionable_earnings)
    stub.ytd_net = _q(ytd_before.net + res.net_pay)
    stub.province_of_employment = emp.province_of_employment
    stub.tables_version = res.tables_version
    stub.notes = inputs.notes
    return stub


def _vacation_accrual_for(stub: PayStub, emp: Employee) -> Decimal:
    """Vacation earned this period but NOT paid out — derived from persisted
    data so approval (a separate request) computes the same number."""
    if emp.vacation_pay_each_period:
        return ZERO
    return _q(Decimal(stub.regular_pay) * Decimal(emp.vacation_pay_pct) / Decimal("100"))


def _cpp_age_exempt(emp: Employee, on: date) -> bool:
    """CPP starts the month after turning 18 and stops the month after turning 70
    (or on CPT30 election — not modelled). No DOB = assume contributing."""
    if not emp.date_of_birth:
        return False
    age = on.year - emp.date_of_birth.year - ((on.month, on.day) < (emp.date_of_birth.month, emp.date_of_birth.day))
    return age < 18 or age >= 70


def _rollup(run: PayrollRun, stubs: list[PayStub]) -> None:
    """Recompute run totals from an explicit stub list. Never touches
    ``run.stubs`` — on a freshly-flushed run that relationship is unloaded and
    accessing it would lazy-load outside the async greenlet."""
    def s(attr):
        return _q(sum((getattr(st, attr) for st in stubs), Decimal("0")))
    run.total_gross = s("gross")
    run.total_vacation_pay = s("vacation_pay")
    run.total_cpp_employee = _q(s("cpp_employee") + s("cpp2_employee"))
    run.total_cpp_employer = _q(s("cpp_employer") + s("cpp2_employer"))
    run.total_ei_employee = _q(s("ei_employee") + s("qpip_employee"))
    run.total_ei_employer = _q(s("ei_employer") + s("qpip_employer"))
    run.total_federal_tax = s("federal_tax")
    run.total_provincial_tax = s("provincial_tax")
    run.total_other_deductions = s("other_deductions")
    run.total_net = s("net_pay")
    run.total_remittance = _q(
        run.total_cpp_employee + run.total_cpp_employer
        + run.total_ei_employee + run.total_ei_employer
        + run.total_federal_tax + run.total_provincial_tax
    )


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


async def list_runs(db: AsyncSession, user: User, *, year: int | None = None) -> list[tuple[PayrollRun, int]]:
    stub_count = select(func.count(PayStub.id)).where(PayStub.run_id == PayrollRun.id).scalar_subquery()
    stmt = select(PayrollRun, stub_count)
    stmt = apply_cashbook_filter(stmt, PayrollRun.user_id, PayrollRun.org_id, user)
    if year:
        stmt = stmt.where(PayrollRun.pay_date >= date(year, 1, 1), PayrollRun.pay_date <= date(year, 12, 31))
    stmt = stmt.order_by(PayrollRun.pay_date.desc(), PayrollRun.created_at.desc())
    return [(r, int(c or 0)) for r, c in (await db.execute(stmt)).all()]


async def get_run(db: AsyncSession, user: User, run_id: uuid.UUID) -> PayrollRun:
    stmt = select(PayrollRun).options(selectinload(PayrollRun.stubs).selectinload(PayStub.employee)).where(PayrollRun.id == run_id)
    stmt = apply_cashbook_filter(stmt, PayrollRun.user_id, PayrollRun.org_id, user)
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise NotFoundError("PayrollRun", str(run_id))
    return run


async def create_run(db: AsyncSession, user: User, data: PayrollRunCreate) -> PayrollRun:
    from app.accounting.period_service import assert_period_open

    await assert_period_open(db, data.pay_date)

    emps = await list_employees(db, user)
    emps = [e for e in emps if e.status == EmployeeStatus.ACTIVE and e.pay_frequency == data.pay_frequency]
    if data.employee_ids is not None:
        wanted = set(data.employee_ids)
        emps = [e for e in emps if e.id in wanted]
    if not emps:
        raise ValidationError("No active employees on that pay frequency.")

    run = PayrollRun(
        user_id=user.id, org_id=_org_id_for(user),
        period_start=data.period_start, period_end=data.period_end, pay_date=data.pay_date,
        pay_frequency=data.pay_frequency, status=PayrollRunStatus.DRAFT, notes=data.notes,
    )
    db.add(run)
    await db.flush()

    overrides = {o.employee_id: o for o in data.overrides}
    stubs: list[PayStub] = []
    for emp in emps:
        stub = await _compute_stub(db, user, run, emp, overrides.get(emp.id), None)
        db.add(stub)
        stubs.append(stub)
    _rollup(run, stubs)
    await db.commit()
    return await get_run(db, user, run.id)


async def recalculate_run(db: AsyncSession, user: User, run_id: uuid.UUID, overrides: list[StubOverride]) -> PayrollRun:
    run = await get_run(db, user, run_id)
    if run.status != PayrollRunStatus.DRAFT:
        raise ConflictError("Only a draft run can be recalculated.")
    ov = {o.employee_id: o for o in overrides}
    stubs = list(run.stubs)  # loaded by get_run's selectinload
    for stub in stubs:
        emp = stub.employee or await get_employee(db, user, stub.employee_id)
        await _compute_stub(db, user, run, emp, ov.get(emp.id), stub)
    _rollup(run, stubs)
    await db.commit()
    return await get_run(db, user, run.id)


# ---------------------------------------------------------------------------
# Approval → journal
# ---------------------------------------------------------------------------


@dataclass
class _Line:
    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal
    description: str | None = None


async def _accounts_by_code(db: AsyncSession, user: User, codes: list[str]) -> dict[str, ChartAccount]:
    """Ensure the tenant's CoA is seeded (idempotent), then map code → account."""
    await coa_service.seed_default_coa(db, user, migrate=False, commit=True)
    stmt = select(ChartAccount).where(ChartAccount.code.in_(codes), ChartAccount.is_active.is_(True))
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    found = {a.code: a for a in (await db.execute(stmt)).scalars().all()}
    missing = [c for c in codes if c not in found]
    if missing:
        raise ValidationError(f"Payroll accounts missing from the chart of accounts: {', '.join(missing)}")
    return found


def _split_remittance(stub: PayStub) -> tuple[Decimal, Decimal]:
    """(to CRA, to Revenu Québec) for one stub — employee + employer statutory."""
    cpp_all = stub.cpp_employee + stub.cpp2_employee + stub.cpp_employer + stub.cpp2_employer
    ei_all = stub.ei_employee + stub.ei_employer
    qpip_all = stub.qpip_employee + stub.qpip_employer
    if stub.province_of_employment == "QC":
        cra = ei_all + stub.federal_tax
        rq = cpp_all + qpip_all + stub.provincial_tax
    else:
        cra = cpp_all + ei_all + stub.federal_tax + stub.provincial_tax
        rq = qpip_all
    return _q(cra), _q(rq)


async def approve_run(db: AsyncSession, user: User, run_id: uuid.UUID) -> PayrollRun:
    run = await get_run(db, user, run_id)
    if run.status != PayrollRunStatus.DRAFT:
        raise ConflictError(f"Run is {run.status.value}; only a draft can be approved.")
    if not run.stubs:
        raise ValidationError("Run has no stubs.")

    acct = await _accounts_by_code(db, user, [
        coa_service.CODE_WAGES_EXPENSE, coa_service.CODE_EMPLOYER_PAYROLL_TAX_EXPENSE,
        coa_service.CODE_PAYROLL_CRA_PAYABLE, coa_service.CODE_PAYROLL_RQ_PAYABLE,
        coa_service.CODE_VACATION_PAYABLE, coa_service.CODE_WAGES_PAYABLE,
        coa_service.CODE_OTHER_DEDUCTIONS_PAYABLE,
    ])

    gross = employer_tax = cra = rq = other = net = accrual = ZERO
    accrual_by_stub: dict[uuid.UUID, Decimal] = {}
    for st in run.stubs:
        gross += st.gross
        employer_tax += st.cpp_employer + st.cpp2_employer + st.ei_employer + st.qpip_employer
        c, r = _split_remittance(st)
        cra += c
        rq += r
        other += st.other_deductions
        net += st.net_pay
        if st.employee:
            acc = _vacation_accrual_for(st, st.employee)
            accrual_by_stub[st.id] = acc
            accrual += acc

    memo = f"Payroll {run.period_start.isoformat()} – {run.period_end.isoformat()} (paid {run.pay_date.isoformat()})"
    lines: list[_Line] = [
        _Line(acct[coa_service.CODE_WAGES_EXPENSE].id, _q(gross + accrual), ZERO, "Gross wages + vacation accrual"),
        _Line(acct[coa_service.CODE_EMPLOYER_PAYROLL_TAX_EXPENSE].id, _q(employer_tax), ZERO, "Employer CPP/EI/QPIP"),
    ]
    if cra:
        lines.append(_Line(acct[coa_service.CODE_PAYROLL_CRA_PAYABLE].id, ZERO, _q(cra), "CRA source deductions + employer share"))
    if rq:
        lines.append(_Line(acct[coa_service.CODE_PAYROLL_RQ_PAYABLE].id, ZERO, _q(rq), "Revenu Québec QPP/QPIP/QC tax"))
    if other:
        lines.append(_Line(acct[coa_service.CODE_OTHER_DEDUCTIONS_PAYABLE].id, ZERO, _q(other), "Other payroll deductions"))
    if accrual:
        lines.append(_Line(acct[coa_service.CODE_VACATION_PAYABLE].id, ZERO, _q(accrual), "Vacation pay accrued"))
    lines.append(_Line(acct[coa_service.CODE_WAGES_PAYABLE].id, ZERO, _q(net), "Net pay owed to employees"))
    lines = [ln for ln in lines if ln.debit or ln.credit]

    entry = await post_journal(
        db, user, date=run.pay_date, lines=lines, memo=memo,
        source="payroll", source_id=str(run.id), commit=False,
    )
    run.journal_entry_id = entry.id
    run.status = PayrollRunStatus.APPROVED
    run.approved_by = user.id
    run.approved_at = datetime.now(timezone.utc)

    # Move accruals onto the employee balance now that they're posted.
    for st in run.stubs:
        acc = accrual_by_stub.get(st.id, ZERO)
        if acc and st.employee:
            st.employee.vacation_accrued_balance = _q(Decimal(st.employee.vacation_accrued_balance or 0) + acc)
    await db.commit()
    return await get_run(db, user, run.id)


async def mark_paid(db: AsyncSession, user: User, run_id: uuid.UUID, *, bank_account_code: str | None = None) -> PayrollRun:
    """Dr Wages Payable / Cr Bank for the net. Cash actually leaving the bank."""
    run = await get_run(db, user, run_id)
    if run.status != PayrollRunStatus.APPROVED:
        raise ConflictError("Only an approved run can be marked paid.")
    code = bank_account_code or coa_service.CODE_BANK
    acct = await _accounts_by_code(db, user, [coa_service.CODE_WAGES_PAYABLE, code])
    lines = [
        _Line(acct[coa_service.CODE_WAGES_PAYABLE].id, _q(run.total_net), ZERO, "Net pay disbursed"),
        _Line(acct[code].id, ZERO, _q(run.total_net), "Payroll paid from bank"),
    ]
    await post_journal(db, user, date=run.pay_date, lines=lines,
                       memo=f"Payroll disbursement {run.pay_date.isoformat()}",
                       source="payroll_paid", source_id=str(run.id), commit=False)
    run.status = PayrollRunStatus.PAID
    run.paid_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_run(db, user, run.id)


async def void_run(db: AsyncSession, user: User, run_id: uuid.UUID) -> PayrollRun:
    """Reverse whatever was posted, flip to VOID. Draft → just VOID."""
    from app.accounting.ledger_models import JournalEntry

    run = await get_run(db, user, run_id)
    if run.status == PayrollRunStatus.VOID:
        return run
    if run.status in _ACTIVE_RUN_STATUSES:
        # Reverse every journal this run produced (approval, and disbursement if paid).
        stmt = select(JournalEntry).options(selectinload(JournalEntry.lines)).where(
            JournalEntry.source.in_(("payroll", "payroll_paid")), JournalEntry.source_id == str(run.id)
        )
        for je in (await db.execute(stmt)).scalars().all():
            rev = [_Line(ln.account_id, ln.credit, ln.debit, f"Reversal: {ln.description or ''}".strip()) for ln in je.lines]
            await post_journal(db, user, date=date.today(), lines=rev,
                               memo=f"VOID payroll run {run.id}", source="payroll_void",
                               source_id=str(run.id), commit=False)
        # Undo vacation accruals
        for st in run.stubs:
            if st.employee and not st.employee.vacation_pay_each_period:
                pct = Decimal(st.employee.vacation_pay_pct) / Decimal("100")
                st.employee.vacation_accrued_balance = _q(
                    max(ZERO, Decimal(st.employee.vacation_accrued_balance or 0) - _q(st.regular_pay * pct))
                )
    run.status = PayrollRunStatus.VOID
    await db.commit()
    return await get_run(db, user, run.id)


# ---------------------------------------------------------------------------
# Preview + remittance
# ---------------------------------------------------------------------------


def preview(req: PreviewRequest) -> PreviewResponse:
    """Pure calc — no DB, no employee. YTD assumed zero (first period of year)."""
    P = PAY_PERIODS[req.pay_frequency]
    if req.pay_type == PayType.HOURLY:
        regular = _q(Decimal(req.hours or 0) * req.pay_rate)
    else:
        regular = _q(req.pay_rate / P)
    vac = _q(regular * Decimal(req.vacation_pay_pct) / Decimal("100"))
    res = calc.compute_period(calc.PeriodInput(
        province=req.province_of_employment, pay_periods=P,
        regular_pay=regular, vacation_pay=vac,
        td1_federal_claim=req.td1_federal_claim, td1_provincial_claim=req.td1_provincial_claim,
        cpp_exempt=req.cpp_exempt, ei_exempt=req.ei_exempt,
    ))
    employer = res.cpp_employer + res.cpp2_employer + res.ei_employer + res.qpip_employer
    return PreviewResponse(
        gross=res.gross,
        cpp_employee=res.cpp_employee, cpp2_employee=res.cpp2_employee,
        ei_employee=res.ei_employee, qpip_employee=res.qpip_employee,
        federal_tax=res.federal_tax, provincial_tax=res.provincial_tax,
        net_pay=res.net_pay,
        employer_cpp=_q(res.cpp_employer + res.cpp2_employer),
        employer_ei=res.ei_employer, employer_qpip=res.qpip_employer,
        total_employer_cost=_q(res.gross + employer),
        annual_taxable_income=res.annual_taxable_income,
        tables_version=res.tables_version,
    )


async def remittance_summary(db: AsyncSession, user: User, *, year: int, month: int) -> RemittanceSummary:
    """PD7A for a calendar month — regular remitter (due the 15th of next month)."""
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    stmt = select(PayrollRun).options(selectinload(PayrollRun.stubs)).where(
        PayrollRun.status.in_(_ACTIVE_RUN_STATUSES),
        PayrollRun.pay_date >= first, PayrollRun.pay_date <= last,
    )
    stmt = apply_cashbook_filter(stmt, PayrollRun.user_id, PayrollRun.org_id, user)
    runs = list((await db.execute(stmt)).scalars().all())

    gross = cpp_e = cpp_r = ei_e = ei_r = tax = cra = rq = ZERO
    employees: set[uuid.UUID] = set()
    for r in runs:
        for st in r.stubs:
            employees.add(st.employee_id)
            gross += st.gross
            c, q_ = _split_remittance(st)
            cra += c
            rq += q_
            if st.province_of_employment != "QC":
                cpp_e += st.cpp_employee + st.cpp2_employee
                cpp_r += st.cpp_employer + st.cpp2_employer
                tax += st.federal_tax + st.provincial_tax
            else:
                tax += st.federal_tax
            ei_e += st.ei_employee
            ei_r += st.ei_employer

    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return RemittanceSummary(
        year=year, month=month, run_count=len(runs), gross_payroll=_q(gross),
        employee_count=len(employees),
        cpp_employee=_q(cpp_e), cpp_employer=_q(cpp_r), ei_employee=_q(ei_e), ei_employer=_q(ei_r),
        income_tax=_q(tax), total_cra=_q(cra), total_revenu_quebec=_q(rq),
        due_date=date(ny, nm, 15),
    )
