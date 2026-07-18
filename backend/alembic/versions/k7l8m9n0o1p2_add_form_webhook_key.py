"""Add forms.webhook_key for inbound lead webhooks

Lets an external website POST lead JSON to /api/forms/webhook/{key} and have it
land in the CRM as a contact + form submission (and fire FORM_SUBMITTED
automations).

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k7l8m9n0o1p2"
down_revision: Union[str, None] = "j6k7l8m9n0o1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive nullable column + a unique index. SQLite creates the index fine;
    # the UNIQUE lives on the index, so no table rebuild is needed.
    op.add_column("forms", sa.Column("webhook_key", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_forms_webhook_key", "forms", ["webhook_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_forms_webhook_key", table_name="forms")
    op.drop_column("forms", "webhook_key")
