
import uuid
from datetime import date, datetime

from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class PlaidConnection(TimestampMixin, Base):
    __tablename__ = "plaid_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    institution_name: Mapped[str] = mapped_column(String(255))
    institution_id: Mapped[str] = mapped_column(String(100))
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    item_id: Mapped[str] = mapped_column(String(255), unique=True)
    sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accounts_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class PlaidConsent(TimestampMixin, Base):
    """Recorded, persisted end-user consent captured BEFORE a bank is connected.

    Schedule 1 requires demonstrable consent. One row per acknowledgement,
    written transactionally with the PlaidConnection it authorizes (see
    service.exchange_public_token). ``created_at`` is the consent timestamp.
    """

    __tablename__ = "plaid_consents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: Tenant/cohort stand-in (org id when present). Plain string so it survives
    #: org deletion — mirrors the audit/event tables.
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Plaid product scope the user authorized, e.g. "transactions".
    product_scope: Mapped[str] = mapped_column(String(100))
    #: Versions referenced at capture time (from app/core/legal.py).
    consent_version: Mapped[str] = mapped_column(String(40))
    privacy_policy_version: Mapped[str] = mapped_column(String(40))
    #: The exact consent copy shown to the user — persisted so we can prove it.
    consent_text: Mapped[str] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Linked to the connection created in the same transaction. SET NULL so
    #: disconnecting a bank doesn't erase the consent record.
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plaid_connections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PlaidTransaction(TimestampMixin, Base):
    __tablename__ = "plaid_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plaid_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plaid_connections.id", ondelete="CASCADE"), index=True
    )
    plaid_transaction_id: Mapped[str] = mapped_column(String(255), unique=True)
    account_id: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(500))
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True
    )
    matched_income_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("income_entries.id", ondelete="SET NULL"), nullable=True
    )
    matched_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    is_categorized: Mapped[bool] = mapped_column(Boolean, default=False)
