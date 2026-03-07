"""Smart Import models."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    PARTIALLY_IMPORTED = "partially_imported"
    IMPORTED = "imported"
    FAILED = "failed"


class ImportItemStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPORTED = "imported"
    DUPLICATE = "duplicate"


class SmartImport(Base):
    __tablename__ = "smart_imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(200))
    file_size: Mapped[int] = mapped_column()
    status: Mapped[ImportStatus] = mapped_column(default=ImportStatus.PENDING)
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    items: Mapped[list["SmartImportItem"]] = relationship(
        back_populates="smart_import", cascade="all, delete-orphan",
        order_by="SmartImportItem.date",
    )


class SmartImportItem(Base):
    __tablename__ = "smart_import_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("smart_imports.id", ondelete="CASCADE")
    )
    status: Mapped[ImportItemStatus] = mapped_column(default=ImportItemStatus.PENDING)
    entry_type: Mapped[str] = mapped_column(String(20))  # income or expense
    date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(String(500))
    amount: Mapped[float] = mapped_column()
    tax_amount: Mapped[float | None] = mapped_column(nullable=True)
    category_suggestion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)  # 0.0 to 1.0
    is_duplicate: Mapped[bool] = mapped_column(default=False)
    duplicate_entry_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    cashbook_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cashbook_entries.id", ondelete="SET NULL"), nullable=True
    )
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    smart_import: Mapped["SmartImport"] = relationship(back_populates="items")
