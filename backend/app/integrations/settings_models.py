import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class IntegrationConfig(TimestampMixin, Base):
    __tablename__ = "integration_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    integration_type: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    encrypted_config: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
