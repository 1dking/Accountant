import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class AccountSubscription(TimestampMixin, Base):
    """A workspace's subscription to O-Brain itself (the SaaS plan the
    customer pays for). One row per account owner. plan_key is the source
    of truth for the current plan; Stripe fields are null on the free tier."""

    __tablename__ = "account_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    plan_key: Mapped[str] = mapped_column(String(20), default="starter")  # starter|pro|business|enterprise
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|canceled|past_due|incomplete
    billing_period: Mapped[str | None] = mapped_column(String(10), nullable=True)  # monthly|annual
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
