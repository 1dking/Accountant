"""SQLAlchemy models for the company settings module."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class CompanySettings(TimestampMixin, Base):
    """Singleton company branding and settings record.

    Only one row should exist. Use get_or_create pattern in the service
    layer to enforce this.
    """

    __tablename__ = "company_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # tax_rates.id is String(36) in the existing schema
    default_tax_rate_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tax_rates.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_currency: Mapped[str] = mapped_column(
        String(3), default="CAD", server_default="CAD"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Relationships
    default_tax_rate = relationship(
        "TaxRate", foreign_keys=[default_tax_rate_id], lazy="selectin"
    )
