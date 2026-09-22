"""cascade job_match_results foreign keys

job_match_results was the only analysis table whose user_id/job_id/
resume_version_id foreign keys were created without ON DELETE CASCADE.
Every sibling table (ats_alignment_results, gap_analyses,
job_eligibility_results, requirement_intelligence, resume_ai_analyses)
cascades, so a Job Match row - a derived, recomputable artifact - was
the one thing pinning a user, job or resume version in place: deleting
any of them raised ForeignKeyViolation once a match had been calculated.

This only replaces the three constraints; no rows are read, written or
removed.

Revision ID: d1e5a8c73b40
Revises: c3f6a1d47e21
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd1e5a8c73b40'
down_revision: Union[str, Sequence[str], None] = 'c3f6a1d47e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FOREIGN_KEYS = (
    ('job_match_results_user_id_fkey', 'user_id', 'users'),
    ('job_match_results_job_id_fkey', 'job_id', 'jobs'),
    (
        'job_match_results_resume_version_id_fkey',
        'resume_version_id',
        'resume_versions',
    ),
)


def upgrade() -> None:
    """Upgrade schema."""
    for constraint_name, column, referent in _FOREIGN_KEYS:
        op.drop_constraint(
            constraint_name, 'job_match_results', type_='foreignkey'
        )
        op.create_foreign_key(
            constraint_name,
            'job_match_results',
            referent,
            [column],
            ['id'],
            ondelete='CASCADE',
        )


def downgrade() -> None:
    """Downgrade schema."""
    for constraint_name, column, referent in _FOREIGN_KEYS:
        op.drop_constraint(
            constraint_name, 'job_match_results', type_='foreignkey'
        )
        op.create_foreign_key(
            constraint_name,
            'job_match_results',
            referent,
            [column],
            ['id'],
        )
