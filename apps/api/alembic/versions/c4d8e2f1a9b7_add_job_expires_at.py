"""add job expires_at

Revision ID: c4d8e2f1a9b7
Revises: a27c0e5b9d13
Create Date: 2026-09-24 16:00:00.000000

AJI-028 (Zero-Cost Job Discovery Foundation). One additive, nullable
column on `jobs`: `expires_at`, the provider-stated closing time of a
discovered posting (naive UTC, like `posting_date`). Existing rows read
as NULL ("no stated expiry"), which keeps every one of them visible - no
backfill, and nothing is inferred for jobs that predate the column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8e2f1a9b7'
down_revision: Union[str, Sequence[str], None] = 'a27c0e5b9d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'jobs',
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('jobs', 'expires_at')
