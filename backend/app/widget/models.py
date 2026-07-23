
import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class WidgetConfig(TimestampMixin, Base):
    """An embeddable lead-capture widget (Arivio port) — a themed skin
    over a hidden Form. widget_key is the embed credential (goes in the
    <script data-widget-key> tag on a third-party site); the linked
    Form's own webhook_key is never exposed to the browser.
    """

    __tablename__ = "widget_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    widget_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    form_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("forms.id", ondelete="CASCADE"))

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    mode: Mapped[str] = mapped_column(String(20), default="floating")  # floating|inline
    position: Mapped[str] = mapped_column(String(20), default="bottom-right")

    button_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bg_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    text_color: Mapped[str | None] = mapped_column(String(20), nullable=True)

    greeting_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    greeting_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    collect_phone: Mapped[bool] = mapped_column(Boolean, default=False)
