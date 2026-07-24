"""Add iso_country + number_type to twilio_phone_numbers

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-24

A2P 10DLC is a US carrier programme: US long codes need an approved campaign,
Canadian long codes are exempt, and toll-free uses Toll-Free Verification
instead. US and CA numbers are BOTH +1, so origin cannot be derived from the
number string — it has to be captured from Twilio and stored.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing rows predate origin capture. NULL classifies as
    # "unknown", which does NOT require 10DLC — refusing to send because we
    # never stored the country would be our bug, not the tenant's. The
    # backfill script fills these from Twilio.
    op.add_column(
        "twilio_phone_numbers",
        sa.Column("iso_country", sa.String(length=2), nullable=True),
    )
    op.add_column(
        "twilio_phone_numbers",
        sa.Column("number_type", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("twilio_phone_numbers", "number_type")
    op.drop_column("twilio_phone_numbers", "iso_country")
