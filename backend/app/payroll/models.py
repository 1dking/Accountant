"""Payroll models: Employee → PayrollRun → PayStub.

Mirrors the SmartImport / SmartImportItem parent-child shape, with the run
linking to the JournalEntry it posted (the way SmartImportItem links to its
CashbookEntry). Tenant-scoped by (user_id, org_id) like ChartAccount so
apply_cashbook_filter works unchanged.

PII: SIN and home address are Fernet-encrypted at rest (EncryptedString).
Name, email, DOB and province stay plaintext — DOB drives the CPP 18–70
exemption window and province drives the tax table, both needed in logic
paths; neither is a secret in the SIN sense.

Money is Numeric(12,2); rates are Numeric(9,4). YTD figures on a stub are a
SNAPSHOT at approval time so a stub never changes after the fact even if an
earlier run is voided.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encrypted_types import EncryptedString
from app.database import Base, TimestampMixin


class PayType(str, enum.Enum):
    HOURLY = "hourly"
    SALARY = "salary"


class PayFrequency(str, enum.Enum):
    WEEKLY = "weekly"            # 52
    BIWEEKLY = "biweekly"        # 26
    SEMIMONTHLY = "semimonthly"  # 24
    MONTHLY = "monthly"          # 12


#: T4127 "P" — pay periods per year.
PAY_PERIODS: dict[PayFrequency, int] = {
    PayFrequency.WEEKLY: 52,
    PayFrequency.BIWEEKLY: 26,
    PayFrequency.SEMIMONTHLY: 24,
    PayFrequency.MONTHLY: 12,
}


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class PayrollRunStatus(str, enum.Enum):
    DRAFT = "draft"          # stubs computed, editable
    APPROVED = "approved"    # journal posted, stubs frozen
    PAID = "paid"            # net pay disbursed (manual mark or bank feed match)
    VOID = "void"            # reversed


class Employee(TimestampMixin, Base):
    __tablename__ = "payroll_employees"
    __table_args__ = (
        Index("ix_payroll_employees_tenant", "user_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    #: Optional link to the CRM contact (an employee who is also a contact).
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    #: Social Insurance Number — 9 digits, encrypted. Printed only on T4/ROE.
    sin: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Home address — encrypted; goes on T4 box "employee's name and address".
    address_line1: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    address_line2: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    #: Home province (ISO-3166-2:CA). Not necessarily the province of employment.
    province: Mapped[str | None] = mapped_column(String(2), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Employment
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[EmployeeStatus] = mapped_column(
        SAEnum(EmployeeStatus), default=EmployeeStatus.ACTIVE, nullable=False
    )
    job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    #: Province of employment — selects the provincial tax table + QPP/QPIP
    #: for QC. T4 box 10.
    province_of_employment: Mapped[str] = mapped_column(String(2), nullable=False, default="ON")

    # Pay
    pay_type: Mapped[PayType] = mapped_column(SAEnum(PayType), nullable=False)
    #: Hourly rate, or annual salary, depending on pay_type.
    pay_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pay_frequency: Mapped[PayFrequency] = mapped_column(SAEnum(PayFrequency), nullable=False)
    #: Default hours per period for hourly staff (stub pre-fills; editable per run).
    default_hours_per_period: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)

    # TD1 claims — the "TC" / "TCP" total claim amounts from the federal and
    # provincial TD1 forms. Default = basic personal amount (filled by service
    # from the tables when NULL).
    td1_federal_claim: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    td1_provincial_claim: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    #: Extra tax the employee asked to withhold per period (TD1 line "additional tax").
    additional_tax_per_period: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, nullable=False, server_default="0"
    )

    # Statutory exemptions
    cpp_exempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    ei_exempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")

    # Vacation
    #: Minimum by province (4% / 6%); overridable per employee.
    vacation_pay_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("4.00"), nullable=False, server_default="4.00"
    )
    #: True = pay out each period; False = accrue and pay on request/termination.
    vacation_pay_each_period: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="1"
    )
    vacation_accrued_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, nullable=False, server_default="0"
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    stubs: Mapped[list["PayStub"]] = relationship(
        back_populates="employee", lazy="noload"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class PayrollRun(TimestampMixin, Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        Index("ix_payroll_runs_tenant_paydate", "user_id", "org_id", "pay_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    #: The cheque date — drives which remittance period + tax year the run
    #: belongs to (CRA counts by pay date, not period end).
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    pay_frequency: Mapped[PayFrequency] = mapped_column(SAEnum(PayFrequency), nullable=False)
    status: Mapped[PayrollRunStatus] = mapped_column(
        SAEnum(PayrollRunStatus), default=PayrollRunStatus.DRAFT, nullable=False
    )

    # Totals (sum of stubs; recomputed on every recalc, frozen at approval)
    total_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_vacation_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_cpp_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_cpp_employer: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_ei_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_ei_employer: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_federal_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_provincial_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_other_deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    #: What goes to CRA on the PD7A for this run: employee CPP+EI+tax + employer CPP+EI.
    total_remittance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    #: The journal entry posted at approval. SET NULL if the entry is deleted.
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    stubs: Mapped[list["PayStub"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin",
        order_by="PayStub.created_at",
    )


class PayStub(TimestampMixin, Base):
    __tablename__ = "payroll_stubs"
    __table_args__ = (
        UniqueConstraint("run_id", "employee_id", name="uq_payroll_stub_run_employee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Inputs for this period
    hours: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    #: Regular earnings before vacation/bonus.
    regular_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    overtime_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    bonus: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    vacation_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    other_earnings: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    #: Gross = regular + overtime + bonus + vacation + other. T4 box 14.
    gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    # Statutory deductions (employee side)
    cpp_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    cpp2_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ei_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    #: QPIP employee premium — Quebec only, else 0.
    qpip_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    federal_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    provincial_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    # Employer side (cost, not deducted from employee)
    cpp_employer: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    cpp2_employer: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ei_employer: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    qpip_employer: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    # Insurable / pensionable bases used (for T4 boxes 24 / 26 and ROE)
    insurable_earnings: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    insurable_hours: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    pensionable_earnings: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    # YTD snapshot AFTER this stub (frozen at approval)
    ytd_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_cpp_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_cpp2_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_ei_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_qpip_employee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_federal_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_provincial_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_insurable_earnings: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_pensionable_earnings: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ytd_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    #: Province of employment at the time of this stub (employee may move).
    province_of_employment: Mapped[str] = mapped_column(String(2), nullable=False)
    #: Which tax-table edition computed this stub, for audit ("2026-01").
    tables_version: Mapped[str] = mapped_column(String(10), nullable=False)
    pdf_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["PayrollRun"] = relationship(back_populates="stubs")
    employee: Mapped["Employee"] = relationship(back_populates="stubs", lazy="selectin")
