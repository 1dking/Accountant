"""fix resourcetype enum casing

Revision ID: ef290c80372d
Revises: d4a1b9e3c567
Create Date: 2026-02-28 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ef290c80372d'
down_revision: Union[str, None] = 'd4a1b9e3c567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # The original migration created the resourcetype enum with lowercase
        # values ('estimate', 'invoice') but SQLAlchemy sends uppercase names
        # ('ESTIMATE', 'INVOICE'). Rename to match.
        result = bind.execute(
            sa.text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'resourcetype'::regtype")
        )
        values = [row[0] for row in result]
        if 'estimate' in values:
            bind.execute(sa.text("ALTER TYPE resourcetype RENAME VALUE 'estimate' TO 'ESTIMATE'"))
        if 'invoice' in values:
            bind.execute(sa.text("ALTER TYPE resourcetype RENAME VALUE 'invoice' TO 'INVOICE'"))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        result = bind.execute(
            sa.text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'resourcetype'::regtype")
        )
        values = [row[0] for row in result]
        if 'ESTIMATE' in values:
            bind.execute(sa.text("ALTER TYPE resourcetype RENAME VALUE 'ESTIMATE' TO 'estimate'"))
        if 'INVOICE' in values:
            bind.execute(sa.text("ALTER TYPE resourcetype RENAME VALUE 'INVOICE' TO 'invoice'"))
