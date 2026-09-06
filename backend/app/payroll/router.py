"""Payroll API. Admin + accountant only — payroll is the most sensitive data
in the books (SINs, pay). Mounted in main.py behind require_business_mode."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_db, require_role
from app.payroll import service
from app.payroll.schemas import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
    EmployeeYTD,
    PayrollRunCreate,
    PayrollRunResponse,
    PayrollRunSummary,
    PayStubResponse,
    PreviewRequest,
    PreviewResponse,
    RemittanceSummary,
    StubOverride,
)

router = APIRouter()

_PayrollUser = Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))]
_DB = Annotated[AsyncSession, Depends(get_db)]


def _run_out(run) -> dict:
    out = PayrollRunResponse.model_validate(run)
    for s_out, s in zip(out.stubs, run.stubs):
        s_out.employee_name = s.employee.full_name if s.employee else None
    return out.model_dump(mode="json")


# ── Employees ──────────────────────────────────────────────────────────────


@router.get("/employees")
async def list_employees(db: _DB, user: _PayrollUser, include_terminated: bool = Query(False)) -> dict:
    emps = await service.list_employees(db, user, include_terminated=include_terminated)
    return {"data": [EmployeeResponse.from_employee(e).model_dump(mode="json") for e in emps]}


@router.post("/employees", status_code=201)
async def create_employee(data: EmployeeCreate, db: _DB, user: _PayrollUser) -> dict:
    emp = await service.create_employee(db, user, data)
    return {"data": EmployeeResponse.from_employee(emp).model_dump(mode="json")}


@router.get("/employees/{employee_id}")
async def get_employee(employee_id: uuid.UUID, db: _DB, user: _PayrollUser) -> dict:
    emp = await service.get_employee(db, user, employee_id)
    return {"data": EmployeeResponse.from_employee(emp).model_dump(mode="json")}


@router.put("/employees/{employee_id}")
async def update_employee(employee_id: uuid.UUID, data: EmployeeUpdate, db: _DB, user: _PayrollUser) -> dict:
    emp = await service.update_employee(db, user, employee_id, data)
    return {"data": EmployeeResponse.from_employee(emp).model_dump(mode="json")}


@router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: uuid.UUID, db: _DB, user: _PayrollUser) -> dict:
    await service.delete_employee(db, user, employee_id)
    return {"data": {"detail": "Employee removed (or terminated if they have pay history)."}}


@router.get("/employees/{employee_id}/ytd")
async def employee_ytd(employee_id: uuid.UUID, db: _DB, user: _PayrollUser, year: int | None = None) -> dict:
    from datetime import date

    await service.get_employee(db, user, employee_id)  # tenancy check
    ytd: EmployeeYTD = await service.employee_ytd(db, user, employee_id, year=year or date.today().year)
    return {"data": ytd.model_dump(mode="json")}


# ── Runs ───────────────────────────────────────────────────────────────────


@router.get("/runs")
async def list_runs(db: _DB, user: _PayrollUser, year: int | None = None) -> dict:
    rows = await service.list_runs(db, user, year=year)
    out = []
    for run, count in rows:
        s = PayrollRunSummary.model_validate(run)
        s.stub_count = count
        out.append(s.model_dump(mode="json"))
    return {"data": out}


@router.post("/runs", status_code=201)
async def create_run(data: PayrollRunCreate, db: _DB, user: _PayrollUser) -> dict:
    run = await service.create_run(db, user, data)
    return {"data": _run_out(run)}


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, db: _DB, user: _PayrollUser) -> dict:
    return {"data": _run_out(await service.get_run(db, user, run_id))}


@router.post("/runs/{run_id}/recalculate")
async def recalculate_run(run_id: uuid.UUID, overrides: list[StubOverride], db: _DB, user: _PayrollUser) -> dict:
    return {"data": _run_out(await service.recalculate_run(db, user, run_id, overrides))}


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: uuid.UUID, db: _DB, user: _PayrollUser) -> dict:
    return {"data": _run_out(await service.approve_run(db, user, run_id))}


@router.post("/runs/{run_id}/mark-paid")
async def mark_paid(run_id: uuid.UUID, db: _DB, user: _PayrollUser, bank_account_code: str | None = None) -> dict:
    return {"data": _run_out(await service.mark_paid(db, user, run_id, bank_account_code=bank_account_code))}


@router.post("/runs/{run_id}/void")
async def void_run(run_id: uuid.UUID, db: _DB, user: _PayrollUser) -> dict:
    return {"data": _run_out(await service.void_run(db, user, run_id))}


@router.get("/runs/{run_id}/stubs/{stub_id}")
async def get_stub(run_id: uuid.UUID, stub_id: uuid.UUID, db: _DB, user: _PayrollUser) -> dict:
    run = await service.get_run(db, user, run_id)
    stub = next((s for s in run.stubs if s.id == stub_id), None)
    if stub is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("PayStub", str(stub_id))
    out = PayStubResponse.model_validate(stub)
    out.employee_name = stub.employee.full_name if stub.employee else None
    return {"data": out.model_dump(mode="json")}


# ── Preview + remittance ───────────────────────────────────────────────────


@router.post("/preview")
async def preview(req: PreviewRequest, _: _PayrollUser) -> dict:
    """What-if calculator. No DB writes."""
    out: PreviewResponse = service.preview(req)
    return {"data": out.model_dump(mode="json")}


@router.get("/remittance")
async def remittance(db: _DB, user: _PayrollUser, year: int, month: int = Query(ge=1, le=12)) -> dict:
    out: RemittanceSummary = await service.remittance_summary(db, user, year=year, month=month)
    return {"data": out.model_dump(mode="json")}
