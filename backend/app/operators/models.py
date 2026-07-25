"""The operator / sub-account primitive — Phase 2 core architecture.

Hierarchy: **Operator → Sub-accounts → End-clients**.

* An **operator** is the agency owner — an existing ``User`` (ADMIN) who provisions
  sub-accounts. There is no separate operator entity; ``SubAccount.operator_user_id``
  points at that user, and a user's world is identified by ``User.operator_id``.
* A **sub-account** is one client's fully isolated tenant under an operator.
* **End-clients** are users whose ``User.sub_account_id`` points at a sub-account.

Isolation is enforced centrally (``app/core/authorization.py``): a user's data is
partitioned by their sub-account (if any) else their operator group. Existing
users carry NULL for both new columns and therefore share one *legacy tenant* —
so behaviour is unchanged until sub-accounts are actually provisioned.

This model is deliberately SEPARATE from the platform-admin ``Organization``
(which stays a superadmin-managed grouping); the operator surface is its own
thing, provisioned by operators, not the platform vendor.
"""

import enum
import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class SubAccountStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"   # operator kill-switch / non-payment
    ARCHIVED = "archived"


class DataEntryMode(str, enum.Enum):
    """Who does the data entry for this sub-account."""

    DOER = "doer"            # the end-client logs in and enters their own data
    RECIPIENT = "recipient"  # the operator builds; the client receives the result


class CrmStyle(str, enum.Enum):
    """How much of the CRM this sub-account exposes."""

    FULL = "full"                    # email / SMS / dialer / pipelines
    CLIENT_STYLE = "client_style"    # contacts + notes only, communication off


class OnboardingTemplate(str, enum.Enum):
    ACCOUNTING_PRACTICE = "accounting_practice"
    MARKETING_AGENCY = "marketing_agency"
    CUSTOM = "custom"


class SubAccount(TimestampMixin, Base):
    """One client's isolated tenant, provisioned by an operator."""

    __tablename__ = "sub_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    #: The operator (agency-owner User) that owns this sub-account.
    operator_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Public slug for branding / booking resolution (globally unique).
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)

    status: Mapped[SubAccountStatus] = mapped_column(
        SAEnum(SubAccountStatus), default=SubAccountStatus.ACTIVE, nullable=False
    )
    data_entry_mode: Mapped[DataEntryMode] = mapped_column(
        SAEnum(DataEntryMode), default=DataEntryMode.DOER, nullable=False
    )
    crm_style: Mapped[CrmStyle] = mapped_column(
        SAEnum(CrmStyle), default=CrmStyle.FULL, nullable=False
    )
    template: Mapped[OnboardingTemplate] = mapped_column(
        SAEnum(OnboardingTemplate), default=OnboardingTemplate.CUSTOM, nullable=False
    )

    # --- White-label branding override (resolved with inheritance in P2.4) ----
    #: NULL means "inherit the operator's brand"; the operator's brand in turn
    #: falls back to the platform default.
    brand_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brand_primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    brand_secondary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    brand_accent_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    brand_font_heading: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand_font_body: Mapped[str | None] = mapped_column(String(100), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    features: Mapped[list["SubAccountFeature"]] = relationship(
        back_populates="sub_account", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("operator_user_id", "name", name="uq_sub_account_operator_name"),
        Index("ix_sub_accounts_operator_status", "operator_user_id", "status"),
    )


class SubAccountFeature(Base):
    """Per-sub-account module toggle. Absence of a row = fall back to the
    template/role default (P2.2 folds these into effective feature resolution).
    ALL modules remain available to every operator at the engine level; this only
    controls which ones a given sub-account receives."""

    __tablename__ = "sub_account_features"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sub_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sub_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_key: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sub_account: Mapped["SubAccount"] = relationship(back_populates="features")

    __table_args__ = (
        UniqueConstraint("sub_account_id", "feature_key", name="uq_sub_account_feature"),
    )
