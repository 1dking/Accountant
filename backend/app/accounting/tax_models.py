"""SQLAlchemy models for sales tax tracking."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaxRate(Base):
    __tablename__ = "tax_rates"
    __table_args__ = (
        Index("ix_tax_rates_type_province", "tax_type", "province"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Free-text legacy label. Kept for backward compat; ``province`` is the
    #: structured field new code should read.
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Canadian tax matrix (all nullable/defaulted so pre-matrix rows keep working) ──
    #: gst | hst | pst | rst | qst | other. NULL on legacy user-created rates.
    tax_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    #: ISO-3166-2:CA code (ON, BC, QC…). NULL = federal (GST) or not province-bound.
    province: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    #: Eligible as an input tax credit on the GST/HST return. GST/HST/QST yes;
    #: BC/SK/MB PST no — it is a cost, not a recoverable tax.
    is_recoverable: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="1"
    )
    #: Seeded by canadian_tax.seed_canadian_tax_rates; not user-deletable.
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )
    #: When this rate took effect (NS 15→14 on 2025-04-01). NULL = always.
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
