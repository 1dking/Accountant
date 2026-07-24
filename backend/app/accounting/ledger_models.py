"""Double-entry ledger spine — Chart of Accounts, journal entries, vendor bills.

Phase 1 (Trustable books): turns the flat category tracker into a real
accounting system without replacing the existing cashbook. Cashbook entries
still post the way they always have; the Chart of Accounts + journal give the
double-entry backbone that a General Ledger and Trial Balance are computed
from (see ledger_reports.py).

Multi-tenant: every table carries user_id + org_id and is scoped through
``apply_cashbook_filter`` — the same isolation the cashbook uses. Account
numbers are unique PER TENANT, never globally (unlike the legacy
TransactionCategory.name unique constraint, which this deliberately does not
copy).

Money is Numeric(14,2) USD.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class AccountType(str, enum.Enum):
    """The five account types — the spine of double-entry. normal_balance
    (which side increases the account) is derived from this."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


#: Which side a type's balance normally sits on. Assets and expenses are debit-
#: normal; liabilities, equity and income are credit-normal. Used by the Trial
#: Balance to place each account's net in the correct column.
NORMAL_BALANCE: dict[AccountType, str] = {
    AccountType.ASSET: "debit",
    AccountType.EXPENSE: "debit",
    AccountType.LIABILITY: "credit",
    AccountType.EQUITY: "credit",
    AccountType.INCOME: "credit",
}


class ChartAccount(TimestampMixin, Base):
    """One account in a tenant's Chart of Accounts.

    ``code`` is the numbered account (e.g. "1000" Cash, "4000" Sales) and is
    unique within the tenant. Everything that posts to the ledger references a
    ChartAccount.
    """

    __tablename__ = "chart_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(SAEnum(AccountType), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: Sub-accounts roll up under a parent (same tenant). NULL = top-level.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chart_accounts.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")
    #: Seeded default accounts — kept even when a tenant customises around them.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", "code", name="uq_chart_account_tenant_code"),
        Index("ix_chart_accounts_tenant_type", "user_id", "account_type"),
    )

    @property
    def normal_balance(self) -> str:
        return NORMAL_BALANCE[self.account_type]


class JournalEntryStatus(str, enum.Enum):
    POSTED = "posted"
    VOID = "void"


class JournalEntry(TimestampMixin, Base):
    """A balanced set of debit/credit lines posted on a date.

    ``source`` records where it came from — "manual" for an operator-posted
    adjusting entry, or "bill" for a vendor-bill posting. Cashbook entries are
    NOT copied into journal entries; the reports expand them on the fly, so the
    two systems never drift.
    """

    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    entry_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[JournalEntryStatus] = mapped_column(
        SAEnum(JournalEntryStatus), default=JournalEntryStatus.POSTED, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", "entry_number", name="uq_journal_entry_tenant_number"),
        Index("ix_journal_entries_tenant_date", "user_id", "date"),
    )


class JournalLine(Base):
    """One debit OR credit against a ChartAccount within a journal entry.

    A line is exactly one side: debit>0 with credit=0, or credit>0 with
    debit=0. The service enforces that and that the entry balances.
    """

    __tablename__ = "journal_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chart_accounts.id"), nullable=False, index=True
    )
    debit: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False, server_default="0")
    credit: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False, server_default="0")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["ChartAccount"] = relationship(lazy="selectin")


class BillStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"      # awaiting approval (client-entered / needs review)
    APPROVED = "approved"    # approved into the books (posts to AP)
    PAID = "paid"
    VOID = "void"


class VendorBill(TimestampMixin, Base):
    """Accounts Payable — money the business owes a vendor.

    The AP counterpart to invoicing (AR). A bill posts Dr expense / Cr Accounts
    Payable on approval, and Dr Accounts Payable / Cr cash on payment.
    """

    __tablename__ = "vendor_bills"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    bill_number: Mapped[str] = mapped_column(String(50), nullable=False)
    #: Vendor is a Contact (type VENDOR). Nullable so a bill can name a vendor
    #: not yet in the CRM.
    vendor_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[BillStatus] = mapped_column(
        SAEnum(BillStatus), default=BillStatus.DRAFT, nullable=False
    )
    #: The AP journal entry created on approval, and the payment entry on pay.
    approval_journal_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    payment_journal_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    scheduled_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    lines: Mapped[list["VendorBillLine"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan", lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", "bill_number", name="uq_vendor_bill_tenant_number"),
    )


class VendorBillLine(Base):
    """One expense/asset line on a vendor bill — posts to a ChartAccount."""

    __tablename__ = "vendor_bill_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendor_bills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chart_accounts.id"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    bill: Mapped["VendorBill"] = relationship(back_populates="lines")
    account: Mapped["ChartAccount"] = relationship(lazy="selectin")
