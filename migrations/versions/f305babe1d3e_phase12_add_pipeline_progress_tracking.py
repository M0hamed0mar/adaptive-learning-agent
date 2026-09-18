"""phase12 add pipeline progress tracking

Revision ID: f305babe1d3e
Revises: caa6e1b8a5f6
Create Date: 2026-09-15 18:05:23.630675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f305babe1d3e'
down_revision: Union[str, Sequence[str], None] = 'caa6e1b8a5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: `pipeline_progress` needs a server_default because SQLite
    # cannot add a NOT NULL column to a table with existing rows
    # without a default value.
    with op.batch_alter_table('study_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pipeline_stage', sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column(
                'pipeline_progress',
                sa.Integer(),
                nullable=False,
                server_default='0',
            )
        )
        batch_op.add_column(sa.Column('pipeline_message', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('study_sessions', schema=None) as batch_op:
        batch_op.drop_column('pipeline_message')
        batch_op.drop_column('pipeline_progress')
        batch_op.drop_column('pipeline_stage')
