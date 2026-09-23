"""add discovery run counters

Revision ID: 5e3a9c1d7f24
Revises: b7d2c9e41a05
Create Date: 2026-09-23 12:00:00.000000

AJI-024 (Job Discovery Product Pipeline). Two additive counters on
`discovery_runs`: `normalized_count` and `duplicate_count`. Both default
to 0 server-side, so existing rows (runs recorded before these counters
existed) read as 0 rather than NULL - no backfill.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e3a9c1d7f24'
down_revision: Union[str, Sequence[str], None] = 'b7d2c9e41a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'discovery_runs',
        sa.Column(
            'normalized_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'discovery_runs',
        sa.Column(
            'duplicate_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade() -> None:
    op.drop_column('discovery_runs', 'duplicate_count')
    op.drop_column('discovery_runs', 'normalized_count')
