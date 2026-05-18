
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SmtpConfig(TimestampMixin, Base):
    __tablename__ = "smtp_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=587)
    username: Mapped[str] = mapped_column(String(255))
    encrypted_password: Mapped[str] = mapped_column(Text)
    from_email: Mapped[str] = mapped_column(String(255))
    from_name: Mapped[str] = mapped_column(String(255))
    use_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class EmailTemplateOverride(TimestampMixin, Base):
    """Per-user override for a system email template.

    ``body_override`` uses plain ``{placeholder}`` substitution, NOT
    Jinja2 — admin-authored content must not be able to escape into
    framework features (loops, includes, attribute lookups). The list
    of allowed placeholders per template_key lives in
    ``app.email.template_schemas``.
    """

    __tablename__ = "email_template_overrides"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    template_key: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_override: Mapped[str | None] = mapped_column(Text, nullable=True)
