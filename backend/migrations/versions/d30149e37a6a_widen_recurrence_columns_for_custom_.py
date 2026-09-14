"""widen recurrence columns for custom intervals

Revision ID: d30149e37a6a
Revises: 782564aabf1a
Create Date: 2026-09-14 13:40:19.194956

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd30149e37a6a'
down_revision: Union[str, Sequence[str], None] = '782564aabf1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite has no ALTER COLUMN TYPE — batch mode does it via the
    # standard SQLite-recommended recreate-table-and-copy dance instead.
    with op.batch_alter_table('pending_clarifications') as batch_op:
        batch_op.alter_column('recurrence',
                   existing_type=sa.VARCHAR(length=10),
                   type_=sa.String(length=20),
                   existing_nullable=True)
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('recurrence',
                   existing_type=sa.VARCHAR(length=10),
                   type_=sa.String(length=20),
                   existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('recurrence',
                   existing_type=sa.String(length=20),
                   type_=sa.VARCHAR(length=10),
                   existing_nullable=True)
    with op.batch_alter_table('pending_clarifications') as batch_op:
        batch_op.alter_column('recurrence',
                   existing_type=sa.String(length=20),
                   type_=sa.VARCHAR(length=10),
                   existing_nullable=True)
