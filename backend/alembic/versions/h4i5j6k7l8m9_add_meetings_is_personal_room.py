"""add meetings.is_personal_room

Personal meeting rooms (Zoom-PMI style) — one persistent meeting row
per user that never moves to COMPLETED. The host pastes its
/m/{slug} link into Calendly / Google Calendar / email signature
and every event reuses the same URL.

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-05-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h4i5j6k7l8m9"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column(
            "is_personal_room",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("meetings", "is_personal_room")
