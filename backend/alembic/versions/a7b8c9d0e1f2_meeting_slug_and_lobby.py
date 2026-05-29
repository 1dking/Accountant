"""Meeting slug + lobby state (Commit 8 — Google-Meet UX parity)

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-05-29

Adds:
  - meetings.slug — 11-char shareable shortcode (abc-defg-hij), unique
  - meetings.scheduled_start — nullable=False → nullable=True (instant
    meetings stamp now() but legacy/template rows can omit)
  - meeting_participants.lobby_status — nullable enum
    {waiting, admitted, denied}. NULL = bypasses lobby (host or pre-
    Commit-8 row already in meeting).

Backfill: existing meetings get a generated slug so the public route
works on day one. No data loss.
"""
import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Merge-and-extend: this revision is a JOIN of two parallel heads that
# existed in production — z6a7b8c9d0e1 (local lineage) and b1c2d3e8
# (VPS lineage, section_variant animations). Adding the slug + lobby
# schema in the same revision unifies them so future migrations have
# a single linear chain.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, tuple, None] = ("z6a7b8c9d0e1", "b1c2d3e8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Match the runtime alphabet — lowercase ASCII letters only.
_SLUG_ALPHABET = "abcdefghijkmnpqrstuvwxyz"  # ambiguous chars (l, o) removed


def _gen_slug() -> str:
    """xxx-xxxx-xxx pattern, 3-4-3 = 10 chars + 2 hyphens = 12 chars
    total. Plenty of entropy (~50 bits) at the alphabet size used."""
    s = "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(10))
    return f"{s[0:3]}-{s[3:7]}-{s[7:10]}"


def upgrade() -> None:
    # --- meetings.slug ------------------------------------------------------
    op.add_column(
        "meetings",
        sa.Column("slug", sa.String(20), nullable=True),
    )
    op.create_index(
        "ix_meetings_slug", "meetings", ["slug"], unique=True,
    )

    # Backfill existing rows with a slug so legacy meetings get a
    # shareable URL too. Conflict-retry is unnecessary at backfill time
    # (the unique index isn't applied to NULLs across DB engines, but
    # we're filling them all here).
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM meetings WHERE slug IS NULL")).fetchall()
    used: set[str] = set()
    for r in rows:
        # Retry to avoid the (astronomically unlikely) collision.
        for _ in range(8):
            candidate = _gen_slug()
            if candidate in used:
                continue
            existing = conn.execute(
                sa.text("SELECT 1 FROM meetings WHERE slug = :s"),
                {"s": candidate},
            ).first()
            if existing is None:
                break
        used.add(candidate)
        conn.execute(
            sa.text("UPDATE meetings SET slug = :s WHERE id = :id"),
            {"s": candidate, "id": r[0]},
        )

    # --- meetings.scheduled_start nullable ---------------------------------
    # SQLite needs batch_alter_table for column-type changes; Postgres
    # handles plain alter. The alembic batch helper papers over both.
    with op.batch_alter_table("meetings") as batch:
        batch.alter_column(
            "scheduled_start",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )

    # --- meeting_participants.lobby_status ---------------------------------
    # Enum stored as a VARCHAR for SQLite portability. Postgres
    # natively maps the Enum type via SQLAlchemy's column reflection
    # without us defining a CREATE TYPE here.
    op.add_column(
        "meeting_participants",
        sa.Column("lobby_status", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("meeting_participants", "lobby_status")
    with op.batch_alter_table("meetings") as batch:
        batch.alter_column(
            "scheduled_start",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
    op.drop_index("ix_meetings_slug", table_name="meetings")
    op.drop_column("meetings", "slug")
