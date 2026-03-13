"""Add is_skipped to gmail_scan_results, composite unique constraint

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_skipped column
    op.add_column(
        "gmail_scan_results",
        sa.Column("is_skipped", sa.Boolean(), server_default="false", nullable=False),
    )

    # Drop the old unique constraint on message_id alone
    op.drop_constraint("gmail_scan_results_message_id_key", "gmail_scan_results", type_="unique")

    # Add composite unique constraint (gmail_account_id, message_id)
    op.create_unique_constraint(
        "uq_gmail_scan_results_account_message",
        "gmail_scan_results",
        ["gmail_account_id", "message_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_gmail_scan_results_account_message", "gmail_scan_results", type_="unique")
    op.create_unique_constraint("gmail_scan_results_message_id_key", "gmail_scan_results", ["message_id"])
    op.drop_column("gmail_scan_results", "is_skipped")
