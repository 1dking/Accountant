from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text
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


class PlaidTransaction(TimestampMixin, Base):
    __tablename__ = "plaid_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plaid_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plaid_connections.id", ondelete="CASCADE"), index=True
    )
    plaid_transaction_id: Mapped[str] = mapped_column(String(255), unique=True)
    account_id: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
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
