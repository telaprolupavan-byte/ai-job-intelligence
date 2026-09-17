"""add job intelligence reference to job match results

Revision ID: 2b9a1d6e4f3c
Revises: 1f71344190a1
Create Date: 2026-09-17 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2b9a1d6e4f3c'
down_revision: Union[str, Sequence[str], None] = '1f71344190a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'job_match_results',
        sa.Column('job_intelligence_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'job_match_results',
        sa.Column(
            'job_content_fingerprint', sa.String(length=64), nullable=True
        ),
    )
    op.create_index(
        op.f('ix_job_match_results_job_intelligence_id'),
        'job_match_results',
        ['job_intelligence_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_job_match_results_job_content_fingerprint'),
        'job_match_results',
        ['job_content_fingerprint'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_job_match_results_job_intelligence_id',
        'job_match_results',
        'job_intelligence',
        ['job_intelligence_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_job_match_results_job_intelligence_id',
        'job_match_results',
        type_='foreignkey',
    )
    op.drop_index(
        op.f('ix_job_match_results_job_content_fingerprint'),
        table_name='job_match_results',
    )
    op.drop_index(
        op.f('ix_job_match_results_job_intelligence_id'),
        table_name='job_match_results',
    )
    op.drop_column('job_match_results', 'job_content_fingerprint')
    op.drop_column('job_match_results', 'job_intelligence_id')
