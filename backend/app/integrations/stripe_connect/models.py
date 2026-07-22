
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class StripeConnectAccount(TimestampMixin, Base):
    """A tenant's own Stripe Express account, connected via Stripe Connect.

    One row per owning user — reconnecting updates this row rather than
    adding a second. No secret/token fields: Express calls always use the
    platform's own stripe_secret_key plus a `stripe_account=` request
    option, never a per-tenant credential (unlike GmailAccount's encrypted
    OAuth tokens).
    """

    __tablename__ = "stripe_connect_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    stripe_account_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    charges_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    payouts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    details_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
