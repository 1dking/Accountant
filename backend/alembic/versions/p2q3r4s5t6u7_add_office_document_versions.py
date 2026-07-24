"""Add office_document_versions table

Point-in-time content_json snapshots for the Docs editor, mirroring the
file-storage module's DocumentVersion table (see
documents/models.py:DocumentVersion). OfficeDocument had no history at
all before this — just whatever content_json holds right now.

Revision ID: p2q3r4s5t6u7
Revises: v8w9x0y1z2a3
Create Date: 2026-07-22

NOTE: originally authored with down_revision o1p2q3r4s5t6, but it sat
uncommitted while the cards/widget/workflow chain (r4s5t6u7v8w9 ..
v8w9x0y1z2a3) landed from that same parent. Re-parented onto the real
head at commit time to keep the chain linear — committing it as-authored
would have produced two heads and failed the deploy's `upgrade head`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p2q3r4s5t6u7"
down_revision: Union[str, None] = "v8w9x0y1z2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "office_document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["office_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "version_number", name="uq_office_doc_version_number"
        ),
    )
    op.create_index(
        "ix_office_document_versions_document_id",
        "office_document_versions",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_office_document_versions_document_id",
        table_name="office_document_versions",
    )
    op.drop_table("office_document_versions")
