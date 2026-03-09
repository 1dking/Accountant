"""SQLAlchemy models for platform administration."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class FeatureFlag(TimestampMixin, Base):
    """Feature flags to enable/disable platform capabilities."""

    __tablename__ = "feature_flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    category: Mapped[str] = mapped_column(String(50), default="general", server_default="general")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class PlatformSetting(TimestampMixin, Base):
    """Key-value platform settings for pricing, limits, and configuration."""

    __tablename__ = "platform_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="general", server_default="general")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), default="string", server_default="string")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ErrorLog(TimestampMixin, Base):
    """Captured application errors for the health dashboard."""

    __tablename__ = "error_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    level: Mapped[str] = mapped_column(String(20), default="error", server_default="error")
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    request_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Organization(TimestampMixin, Base):
    """Organizations for multi-tenant management."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    plan: Mapped[str] = mapped_column(String(50), default="starter", server_default="starter")
    max_users: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    max_storage_gb: Mapped[int] = mapped_column(Integer, default=5, server_default="5")

    # White-label
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    custom_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    feature_overrides: Mapped[list["OrgFeatureOverride"]] = relationship(
        "OrgFeatureOverride", back_populates="organization", cascade="all, delete-orphan", lazy="selectin"
    )
    setting_overrides: Mapped[list["OrgSettingOverride"]] = relationship(
        "OrgSettingOverride", back_populates="organization", cascade="all, delete-orphan", lazy="selectin"
    )


class OrgFeatureOverride(TimestampMixin, Base):
    """Per-org feature flag overrides. Overrides the global feature_flags default."""

    __tablename__ = "org_feature_overrides"
    __table_args__ = (
        UniqueConstraint("org_id", "feature_key", name="uq_org_feature_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="feature_overrides"
    )


class OrgSettingOverride(TimestampMixin, Base):
    """Per-org setting overrides. Overrides the global platform_settings default."""

    __tablename__ = "org_setting_overrides"
    __table_args__ = (
        UniqueConstraint("org_id", "setting_key", name="uq_org_setting_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="setting_overrides"
    )
