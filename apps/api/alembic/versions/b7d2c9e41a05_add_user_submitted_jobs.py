"""add user submitted jobs

Revision ID: b7d2c9e41a05
Revises: 811edbdfe2e8
Create Date: 2026-09-22 12:00:00.000000

AJI-022 (User Job Submission). Two additive, nullable columns on `jobs`:

1. `submitted_by_user_id` - NULL means a discovered job shared with every
   user, which is exactly what every existing row already is, so no
   backfill is needed. A user id marks a job that user pasted in; it is
   private to them. `ON DELETE CASCADE` so deleting a user removes their
   private jobs (and, through the existing job FKs, everything derived
   from them) rather than orphaning private data as "shared".
2. `raw_submitted_content` - the pasted content verbatim. NULL for every
   discovered job.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d2c9e41a05'
down_revision: Union[str, Sequence[str], None] = '811edbdfe2e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SUBMITTED_BY_FK = "fk_jobs_submitted_by_user_id"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'jobs',
        sa.Column('submitted_by_user_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'jobs',
        sa.Column('raw_submitted_content', sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        SUBMITTED_BY_FK,
        'jobs',
        'users',
        ['submitted_by_user_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index(
        op.f('ix_jobs_submitted_by_user_id'),
        'jobs',
        ['submitted_by_user_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    Private submitted jobs are deleted first: dropping the owner column
    would otherwise silently turn every one of them into a shared,
    discovered job visible to all users.
    """
    op.execute("DELETE FROM jobs WHERE submitted_by_user_id IS NOT NULL")
    op.drop_index(op.f('ix_jobs_submitted_by_user_id'), table_name='jobs')
    op.drop_constraint(SUBMITTED_BY_FK, 'jobs', type_='foreignkey')
    op.drop_column('jobs', 'raw_submitted_content')
    op.drop_column('jobs', 'submitted_by_user_id')
