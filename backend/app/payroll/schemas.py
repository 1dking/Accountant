"""Pydantic schemas for payroll."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.payroll.models import EmployeeStatus, PayFrequency, PayrollRunStatus, PayType

_SIN_LEN = 9


def _clean_sin(v: str | None) -> str | None:
    if v is None:
        return None
    digits = "".join(ch for ch in v if ch.isdigit())
    if not digits:
        return None
    if len(digits) != _SIN_LEN:
        raise ValueError("SIN must be 9 digits")
    # Luhn check — CRA SINs validate under mod-10.
    total = 0
    for i, ch in enumerate(digits):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    if total % 10 != 0:
        raise ValueError("SIN failed checksum")
    return digits


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------


class EmployeeBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    date_of_birth: date | None = None
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    province: str | None = Field(None, min_length=2, max_length=2)
    postal_code: str | None = Field(None, max_length=10)
    job_title: str | None = Field(None, max_length=150)
    province_of_employment: str = Field("ON", min_length=2, max_length=2)
    pay_type: PayType
    pay_rate: Decimal = Field(gt=0)
    pay_frequency: PayFrequency
    default_hours_per_period: Decimal | None = Field(None, ge=0, le=400)
    td1_federal_claim: Decimal | None = Field(None, ge=0)
    td1_provincial_claim: Decimal | None = Field(None, ge=0)
    additional_tax_per_period: Decimal = Field(Decimal("0"), ge=0)
    cpp_exempt: bool = False
    ei_exempt: bool = False
    vacation_pay_pct: Decimal = Field(Decimal("4.00"), ge=0, le=20)
    vacation_pay_each_period: bool = True
    notes: str | None = None
    contact_id: uuid.UUID | None = None

    @field_validator("province", "province_of_employment", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class EmployeeCreate(EmployeeBase):
    hire_date: date
    sin: str | None = None

    @field_validator("sin", mode="before")
    @classmethod
    def _sin(cls, v):
        return _clean_sin(v)


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    sin: str | None = None
    date_of_birth: date | None = None
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    province: str | None = Field(None, min_length=2, max_length=2)
    postal_code: str | None = Field(None, max_length=10)
    hire_date: date | None = None
    termination_date: date | None = None
    status: EmployeeStatus | None = None
    job_title: str | None = Field(None, max_length=150)
    province_of_employment: str | None = Field(None, min_length=2, max_length=2)
    pay_type: PayType | None = None
    pay_rate: Decimal | None = Field(None, gt=0)
    pay_frequency: PayFrequency | None = None
    default_hours_per_period: Decimal | None = Field(None, ge=0, le=400)
    td1_federal_claim: Decimal | None = Field(None, ge=0)
    td1_provincial_claim: Decimal | None = Field(None, ge=0)
    additional_tax_per_period: Decimal | None = Field(None, ge=0)
    cpp_exempt: bool | None = None
    ei_exempt: bool | None = None
    vacation_pay_pct: Decimal | None = Field(None, ge=0, le=20)
    vacation_pay_each_period: bool | None = None
    notes: str | None = None
    contact_id: uuid.UUID | None = None

    @field_validator("sin", mode="before")
    @classmethod
    def _sin(cls, v):
        return _clean_sin(v)

    @field_validator("province", "province_of_employment", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class EmployeeResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str
    email: str | None
    phone: str | None
    #: Masked — "***-***-123". Full SIN never leaves the server except on T4/ROE.
    sin_masked: str | None = None
    date_of_birth: date | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    province: str | None
    postal_code: str | None
    hire_date: date
    termination_date: date | None
    status: EmployeeStatus
    job_title: str | None
    province_of_employment: str
    pay_type: PayType
    pay_rate: Decimal
    pay_frequency: PayFrequency
    default_hours_per_period: Decimal | None
    td1_federal_claim: Decimal | None
    td1_provincial_claim: Decimal | None
    additional_tax_per_period: Decimal
    cpp_exempt: bool
    ei_exempt: bool
    vacation_pay_pct: Decimal
    vacation_pay_each_period: bool
    vacation_accrued_balance: Decimal
    notes: str | None
    contact_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_employee(cls, e) -> "EmployeeResponse":
        obj = cls.model_validate(e)
        sin = getattr(e, "sin", None)
        obj.sin_masked = f"***-***-{sin[-3:]}" if sin and len(sin) >= 3 else None
        return obj


# ---------------------------------------------------------------------------
# Runs + stubs
# ---------------------------------------------------------------------------


class StubOverride(BaseModel):
    """Per-employee inputs for a run. Anything omitted uses the employee default."""
    employee_id: uuid.UUID
    hours: Decimal | None = Field(None, ge=0, le=400)
    overtime_pay: Decimal = Field(Decimal("0"), ge=0)
    bonus: Decimal = Field(Decimal("0"), ge=0)
    other_earnings: Decimal = Field(Decimal("0"), ge=0)
    other_deductions: Decimal = Field(Decimal("0"), ge=0)
    #: Pay out accrued vacation this period (on top of the regular %).
    vacation_payout: Decimal = Field(Decimal("0"), ge=0)
    notes: str | None = None


class PayrollRunCreate(BaseModel):
    period_start: date
    period_end: date
    pay_date: date
    pay_frequency: PayFrequency
    #: Restrict to these employees; default = every active employee on this frequency.
    employee_ids: list[uuid.UUID] | None = None
    overrides: list[StubOverride] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("period_end")
    @classmethod
    def _end_after_start(cls, v, info):
        start = info.data.get("period_start")
        if start and v < start:
            raise ValueError("period_end must be on or after period_start")
        return v


class PayStubResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    hours: Decimal | None
    rate: Decimal
    regular_pay: Decimal
    overtime_pay: Decimal
    bonus: Decimal
    vacation_pay: Decimal
    other_earnings: Decimal
    gross: Decimal
    cpp_employee: Decimal
    cpp2_employee: Decimal
    ei_employee: Decimal
    qpip_employee: Decimal
    federal_tax: Decimal
    provincial_tax: Decimal
    other_deductions: Decimal
    net_pay: Decimal
    cpp_employer: Decimal
    cpp2_employer: Decimal
    ei_employer: Decimal
    qpip_employer: Decimal
    insurable_earnings: Decimal
    insurable_hours: Decimal
    pensionable_earnings: Decimal
    ytd_gross: Decimal
    ytd_cpp_employee: Decimal
    ytd_cpp2_employee: Decimal
    ytd_ei_employee: Decimal
    ytd_qpip_employee: Decimal
    ytd_federal_tax: Decimal
    ytd_provincial_tax: Decimal
    ytd_insurable_earnings: Decimal
    ytd_pensionable_earnings: Decimal
    ytd_net: Decimal
    province_of_employment: str
    tables_version: str
    pdf_storage_path: str | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class PayrollRunResponse(BaseModel):
    id: uuid.UUID
    period_start: date
    period_end: date
    pay_date: date
    pay_frequency: PayFrequency
    status: PayrollRunStatus
    total_gross: Decimal
    total_vacation_pay: Decimal
    total_cpp_employee: Decimal
    total_cpp_employer: Decimal
    total_ei_employee: Decimal
    total_ei_employer: Decimal
    total_federal_tax: Decimal
    total_provincial_tax: Decimal
    total_other_deductions: Decimal
    total_net: Decimal
    total_remittance: Decimal
    journal_entry_id: uuid.UUID | None
    approved_at: datetime | None
    paid_at: datetime | None
    notes: str | None
    stubs: list[PayStubResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollRunSummary(BaseModel):
    """List-row shape — no stubs."""
    id: uuid.UUID
    period_start: date
    period_end: date
    pay_date: date
    pay_frequency: PayFrequency
    status: PayrollRunStatus
    total_gross: Decimal
    total_net: Decimal
    total_remittance: Decimal
    stub_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Preview (calc-only) + remittance + YTD
# ---------------------------------------------------------------------------


class PreviewRequest(BaseModel):
    """What-if: no employee record needed. Powers the 'how much does a $60k
    hire cost me' calculator on the pricing/marketing page too."""
    province_of_employment: str = Field("ON", min_length=2, max_length=2)
    pay_frequency: PayFrequency = PayFrequency.BIWEEKLY
    pay_type: PayType = PayType.SALARY
    pay_rate: Decimal = Field(gt=0)
    hours: Decimal | None = Field(None, ge=0, le=400)
    vacation_pay_pct: Decimal = Field(Decimal("4.00"), ge=0, le=20)
    td1_federal_claim: Decimal | None = None
    td1_provincial_claim: Decimal | None = None
    cpp_exempt: bool = False
    ei_exempt: bool = False

    @field_validator("province_of_employment", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class PreviewResponse(BaseModel):
    gross: Decimal
    cpp_employee: Decimal
    cpp2_employee: Decimal
    ei_employee: Decimal
    qpip_employee: Decimal
    federal_tax: Decimal
    provincial_tax: Decimal
    net_pay: Decimal
    employer_cpp: Decimal
    employer_ei: Decimal
    employer_qpip: Decimal
    #: Gross + employer contributions — what this period truly costs.
    total_employer_cost: Decimal
    annual_taxable_income: Decimal
    tables_version: str


class RemittanceSummary(BaseModel):
    """PD7A figures for one remittance period (calendar month)."""
    year: int
    month: int
    run_count: int
    gross_payroll: Decimal
    employee_count: int
    cpp_employee: Decimal
    cpp_employer: Decimal
    ei_employee: Decimal
    ei_employer: Decimal
    income_tax: Decimal          # federal + provincial (non-QC)
    total_cra: Decimal
    #: Quebec: QPP + QPIP + QC tax, remitted to Revenu Québec separately.
    total_revenu_quebec: Decimal
    #: 15th of the following month for regular remitters.
    due_date: date


class EmployeeYTD(BaseModel):
    employee_id: uuid.UUID
    year: int
    gross: Decimal
    cpp_employee: Decimal
    cpp2_employee: Decimal
    ei_employee: Decimal
    qpip_employee: Decimal
    federal_tax: Decimal
    provincial_tax: Decimal
    insurable_earnings: Decimal
    insurable_hours: Decimal
    pensionable_earnings: Decimal
    net: Decimal
    stub_count: int
