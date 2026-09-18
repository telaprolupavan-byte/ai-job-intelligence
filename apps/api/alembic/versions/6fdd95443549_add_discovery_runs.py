"""add discovery runs

Revision ID: 6fdd95443549
Revises: 359fa3edc371
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6fdd95443549'
down_revision: Union[str, Sequence[str], None] = '359fa3edc371'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'discovery_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('fetched_count', sa.Integer(), nullable=False),
        sa.Column('inserted_count', sa.Integer(), nullable=False),
        sa.Column('updated_count', sa.Integer(), nullable=False),
        sa.Column('rejected_count', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_discovery_runs_started_at'),
        'discovery_runs',
        ['started_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_discovery_runs_started_at'),
        table_name='discovery_runs',
    )
    op.drop_table('discovery_runs')
