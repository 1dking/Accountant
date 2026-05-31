"""add branding_settings.logo_storage_path

Tracks the storage backend path (R2 key or local-disk path) where the
uploaded brand logo lives. Previously the upload endpoint pushed bytes
to R2 directly and stuffed the API endpoint URL into logo_url — but
that URL isn't publicly fetchable without a custom domain, so logos
silently failed to render. We now mirror the company-logo pattern:
write through storage.save(), persist the returned path here, and
stream bytes from a public GET endpoint.

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-05-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "g3h4i5j6k7l8"
down_revision = "f2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branding_settings",
        sa.Column("logo_storage_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("branding_settings", "logo_storage_path")
