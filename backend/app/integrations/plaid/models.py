
import uuid
from datetime import date, datetime

from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.encrypted_types import EncryptedNumeric, EncryptedString
from app.database import Base, TimestampMixin

# NOTE: consumer-financial fields below use EncryptedString/EncryptedNumeric —
# encrypted at rest with the app's Fernet key. Fields kept plaintext (date,
# plaid_transaction_id, item_id, institution_id, sync_cursor, booleans) are
# either non-sensitive/opaque or required in SQL WHERE/ORDER BY; see
# ENCRYPTION_AT_REST.md for the rationale and the at-rest migration.


class PlaidConnection(TimestampMixin, Base):
    __tablename__ = "plaid_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    institution_name: Mapped[str] = mapped_column(EncryptedString)  # bank name — encrypted
    institution_id: Mapped[str] = mapped_column(String(100))  # opaque Plaid id — plaintext
    encrypted_access_token: Mapped[str] = mapped_column(Text)  # already Fernet-encrypted
    item_id: Mapped[str] = mapped_column(String(255), unique=True)  # opaque, unique — plaintext
    sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)  # opaque cursor
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Account metadata incl. names + mask (last 4) — encrypted.
    accounts_json: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)


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
    # Opaque Plaid id — plaintext (unique + used for dedup lookups).
    plaid_transaction_id: Mapped[str] = mapped_column(String(255), unique=True)
    account_id: Mapped[str] = mapped_column(EncryptedString)  # account identifier — encrypted
    amount: Mapped[Decimal] = mapped_column(EncryptedNumeric)  # dollar amount — encrypted
    date: Mapped[date] = mapped_column(Date, index=True)  # plaintext — range-filtered + ordered
    name: Mapped[str] = mapped_column(EncryptedString)  # payee/description — encrypted
    merchant_name: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)  # encrypted
    category: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)  # encrypted
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
    # Bank Scanner: set when this transaction is posted to the Cashbook (the
    # primary destination), mirroring matched_expense_id/matched_income_id so
    # the UI can show "Posted to Cashbook".
    matched_cashbook_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cashbook_entries.id", ondelete="SET NULL"), nullable=True
    )
    is_categorized: Mapped[bool] = mapped_column(Boolean, default=False)
