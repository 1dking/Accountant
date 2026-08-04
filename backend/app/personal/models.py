"""Personal ledger — a per-user, encrypted, private personal-finance book.

Kept in SEPARATE tables from the business cashbook by design (see the approved
plan): business reports (P&L, tax, marketing) query CashbookEntry/JournalEntry
and NEVER these tables, so personal money cannot leak into business totals by
construction — there is no shared filter to get wrong. And because the chosen
requirement is to encrypt personal amounts + descriptions at rest, they need
their own storage anyway: CashbookEntry.total_amount is a plaintext Numeric that
business SQL sums, whereas EncryptedNumeric is Text-backed and cannot be summed
in SQL — the two can't share one column.

Personal data is ALWAYS private to the individual (scoped by user_id, never
org-shared), so there is no org_id here even in a shared business org.

Encryption: description + amount use the same Fernet column types as the Plaid
tables (app/core/encrypted_types). Kept plaintext for query/order: date,
direction, account_id, and opaque source ids — the identical tradeoff documented
in app/integrations/plaid/models.py.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encrypted_types import EncryptedNumeric, EncryptedString
from app.database import Base, TimestampMixin


class PersonalAccount(TimestampMixin, Base):
    """A genuinely personal account (a personal chequing card, a wallet). Never
    org-shared; visible only to its owner."""

    __tablename__ = "personal_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(EncryptedString, nullable=False)  # encrypted
    account_type: Mapped[str] = mapped_column(String(30), default="bank", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(EncryptedNumeric, nullable=False)  # encrypted
    opening_balance_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    # Opaque key that ties an auto-provisioned mirror account back to its source
    # (e.g. a Plaid account id) so a shared bank feed's personal copies all land
    # in one personal account. Plaintext (not PII) + indexed for get-or-create.
    external_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    entries: Mapped[list["PersonalTransaction"]] = relationship(
        "PersonalTransaction", back_populates="account", lazy="selectin"
    )


class PersonalCategory(TimestampMixin, Base):
    """Personal-finance category (Groceries, Rent, Salary…). Kept entirely apart
    from the global business TransactionCategory table. A NULL user_id marks a
    seeded default available to everyone; a set user_id is a user's own."""

    __tablename__ = "personal_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    #: 'in' | 'out' | 'both' — which side this category applies to.
    direction: Mapped[str] = mapped_column(String(4), default="both", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PersonalTransaction(TimestampMixin, Base):
    """One personal money movement. amount + description are encrypted at rest;
    date/direction/account_id stay plaintext so the ledger can be filtered and
    ordered in SQL. Aggregation (cashflow totals) decrypts in Python, at
    one-person scale — mirroring plaid reconciliation_summary."""

    __tablename__ = "personal_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("personal_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # plaintext
    #: 'in' (money received) | 'out' (money spent) — plaintext, drives the sign.
    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(EncryptedNumeric, nullable=False)  # encrypted
    description: Mapped[str] = mapped_column(EncryptedString, nullable=False)  # encrypted
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("personal_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)  # encrypted
    # Opaque provenance (e.g. a Plaid transaction id in Phase 2) — plaintext, for
    # idempotency lookups. Never PII.
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")

    account: Mapped[PersonalAccount] = relationship(
        "PersonalAccount", back_populates="entries", lazy="selectin"
    )
    category: Mapped[PersonalCategory | None] = relationship("PersonalCategory", lazy="selectin")
