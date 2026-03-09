"""SQLAlchemy models for the cashbook module."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AccountType(str, enum.Enum):
    BANK = "bank"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    SAVINGS = "savings"
    LOAN = "loan"
    PAYPAL = "paypal"
    OTHER = "other"


class EntryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class EntryStatus(str, enum.Enum):
    PENDING = "pending"
    CLEARED = "cleared"
    RECONCILED = "reconciled"
    VOIDED = "voided"


class CategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    BOTH = "both"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TransactionCategory(TimestampMixin, Base):
    __tablename__ = "transaction_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category_type: Mapped[CategoryType] = mapped_column(
        Enum(CategoryType), nullable=False
    )
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class PaymentAccount(TimestampMixin, Base):
    __tablename__ = "payment_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    opening_balance_date: Mapped[date] = mapped_column(Date, nullable=False)
    default_tax_rate_id: Mapped[str | None] = mapped_column(
        ForeignKey("tax_rates.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    entries: Mapped[list["CashbookEntry"]] = relationship(
        "CashbookEntry", back_populates="account", lazy="selectin"
    )


class CashbookEntry(TimestampMixin, Base):
    __tablename__ = "cashbook_entries"
    __table_args__ = (
        Index("ix_cashbook_entries_account_date", "account_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Amount fields
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    tax_override: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Category
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transaction_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Links
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    # Source tracking
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Status tracking
    status: Mapped[EntryStatus] = mapped_column(
        Enum(EntryStatus), nullable=False, default=EntryStatus.PENDING, server_default="pending"
    )

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Split transaction support
    split_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cashbook_entries.id", ondelete="CASCADE"), nullable=True
    )

    # Relationships
    account: Mapped[PaymentAccount] = relationship(
        "PaymentAccount", back_populates="entries", lazy="selectin"
    )
    category: Mapped[TransactionCategory | None] = relationship(
        "TransactionCategory", lazy="selectin"
    )
    split_children: Mapped[list["CashbookEntry"]] = relationship(
        "CashbookEntry", back_populates="split_parent", lazy="selectin",
        foreign_keys="CashbookEntry.split_parent_id",
    )
    split_parent: Mapped["CashbookEntry | None"] = relationship(
        "CashbookEntry", back_populates="split_children", lazy="selectin",
        remote_side="CashbookEntry.id",
        foreign_keys="CashbookEntry.split_parent_id",
    )
