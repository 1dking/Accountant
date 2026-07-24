"""SQLAlchemy models for the office module."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DocType(str, enum.Enum):
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"


class Permission(str, enum.Enum):
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class OfficeDocument(TimestampMixin, Base):
    __tablename__ = "office_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), default="Untitled", nullable=False)
    doc_type: Mapped[DocType] = mapped_column(Enum(DocType), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    yjs_state: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_starred: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    is_trashed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    trashed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    access_list: Mapped[list["OfficeDocumentAccess"]] = relationship(
        "OfficeDocumentAccess",
        back_populates="document",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class OfficeDocumentAccess(Base):
    __tablename__ = "office_document_access"
    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_office_doc_access"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("office_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission: Mapped[Permission] = mapped_column(
        Enum(Permission), default=Permission.VIEW, nullable=False
    )
    granted_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    document: Mapped[OfficeDocument] = relationship(
        "OfficeDocument", back_populates="access_list"
    )


class OfficeDocumentVersion(Base):
    """A point-in-time content_json snapshot. Created automatically on a
    throttled cadence during editing (see service.snapshot_version_if_due)
    and on-demand via the "Save version" action, mirroring the file-storage
    module's DocumentVersion pattern (app/documents/models.py).
    """

    __tablename__ = "office_document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_number", name="uq_office_doc_version_number"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("office_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OfficeDocumentComment(TimestampMixin, Base):
    """A comment (optionally threaded via parent_id) on a document, mirroring
    app/collaboration/models.py:Comment. A separate table rather than
    reusing Comment directly -- Comment.document_id FKs to the file-storage
    documents table, not office_documents.
    """

    __tablename__ = "office_document_comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("office_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("office_document_comments.id", ondelete="CASCADE"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
