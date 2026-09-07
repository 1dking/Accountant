"""SQLAlchemy models for the company settings module."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
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

    # ── Canadian tax identity ──
    #: ISO-3166-2:CA code (ON, BC, QC…). Drives default GST/HST/PST/QST rates via
    #: canadian_tax.rates_for_province. ``state`` above stays for US-shaped
    #: addresses and legacy rows; new Canadian code reads ``province``.
    province: Mapped[str | None] = mapped_column(String(2), nullable=True)
    #: CRA Business Number — 9 digits (123456789). Printed on T2125/T2/T4.
    business_number: Mapped[str | None] = mapped_column(String(15), nullable=True)
    #: GST/HST program account — usually BN + "RT0001". Printed on invoices
    #: (required once registered) and the GST34.
    gst_hst_number: Mapped[str | None] = mapped_column(String(15), nullable=True)
    #: 1–12. Sole props are calendar-year (12); corporations pick their own.
    fiscal_year_end_month: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    # S5 site content — used by the page builder's data resolvers. Never
    # touched by the accounting side. Org-scoped so operator sub-accounts
    # can each have their own public profile.
    org_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_hours_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_area_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    map_embed_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    brand_primary_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    booking_calendar_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_form_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    # Relationships
    default_tax_rate = relationship(
        "TaxRate", foreign_keys=[default_tax_rate_id], lazy="selectin"
    )
