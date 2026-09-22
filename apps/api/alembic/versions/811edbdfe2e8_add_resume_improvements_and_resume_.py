"""add resume improvements and resume version lineage

Revision ID: 811edbdfe2e8
Revises: d1e5a8c73b40
Create Date: 2026-09-22 03:45:52.939265

AJI-021 (Resume Improvement Approval & Recheck). Three changes:

1. `resume_improvements` - the new approval/recheck record. Its
   `(user_id, gap_analysis_id, approval_fingerprint)` unique constraint
   is what makes duplicate approval/version creation impossible in the
   database itself, not only in application code.
2. `resume_versions.parent_version_id` / `.source` - the parent/child
   lineage. Both are additive and nullable/defaulted, so every existing
   row keeps its exact current meaning (an uploaded version with no
   parent).
3. `resume_versions.storage_path` is widened to NULL-able. An uploaded
   version always has a stored file; a version generated from approved
   improvements has no source document on disk. This only widens the
   column - no existing row is read or rewritten.

Note on the downgrade: step 3 cannot be reversed while any generated
version exists (those rows have no `storage_path` to restore, and
inventing one would point at a file that was never written), so the
downgrade deletes improvement-sourced versions along with the
`resume_improvements` rows that reference them. Uploaded versions are
never touched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '811edbdfe2e8'
# Originally c3f6a1d47e21. d1e5a8c73b40 (PR #60) branched off the same
# revision and merged first, so once PR #61 merged, main carried two
# alembic heads and `alembic upgrade head` failed outright on a fresh
# database. Re-pointed onto d1e5a8c73b40 to linearize the chain.
#
# Safe to re-point rather than add a merge revision, on two counts:
#
# 1. Neither migration depends on the other's changes, so the order is
#    immaterial. d1e5a8c73b40 only ALTERS `job_match_results`
#    (re-creating three foreign keys); it touches `resume_versions`
#    solely as an FK target on `id`. This one creates
#    `resume_improvements` and alters `resume_versions`, never touching
#    `job_match_results` or `resume_versions.id`.
# 2. No environment can have applied this revision at its old parent,
#    because main was unmigratable for the entire window in which that
#    parent existed - there is no deployed `alembic_version` row to
#    strand.
down_revision: Union[str, Sequence[str], None] = 'd1e5a8c73b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RESUME_VERSION_PARENT_FK = "fk_resume_versions_parent_version_id"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'resume_improvements',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('gap_analysis_id', sa.UUID(), nullable=False),
        sa.Column('baseline_ats_alignment_id', sa.UUID(), nullable=False),
        sa.Column('parent_resume_version_id', sa.UUID(), nullable=False),
        sa.Column('child_resume_version_id', sa.UUID(), nullable=False),
        sa.Column('approval_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('engine_version', sa.String(length=50), nullable=False),
        sa.Column('approved_count', sa.Integer(), nullable=False),
        sa.Column('skipped_count', sa.Integer(), nullable=False),
        sa.Column('recheck_status', sa.String(length=20), nullable=False),
        sa.Column('recheck_error', sa.Text(), nullable=True),
        sa.Column('recheck_ats_alignment_id', sa.UUID(), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['baseline_ats_alignment_id'], ['ats_alignment_results.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['child_resume_version_id'], ['resume_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['gap_analysis_id'], ['gap_analyses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_resume_version_id'], ['resume_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recheck_ats_alignment_id'], ['ats_alignment_results.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id',
            'gap_analysis_id',
            'approval_fingerprint',
            name='uq_resume_improvement_user_gap_fingerprint',
        ),
    )
    op.create_index(op.f('ix_resume_improvements_approval_fingerprint'), 'resume_improvements', ['approval_fingerprint'], unique=False)
    op.create_index(op.f('ix_resume_improvements_baseline_ats_alignment_id'), 'resume_improvements', ['baseline_ats_alignment_id'], unique=False)
    op.create_index(op.f('ix_resume_improvements_child_resume_version_id'), 'resume_improvements', ['child_resume_version_id'], unique=False)
    op.create_index(op.f('ix_resume_improvements_gap_analysis_id'), 'resume_improvements', ['gap_analysis_id'], unique=False)
    op.create_index(op.f('ix_resume_improvements_job_id'), 'resume_improvements', ['job_id'], unique=False)
    op.create_index(op.f('ix_resume_improvements_parent_resume_version_id'), 'resume_improvements', ['parent_resume_version_id'], unique=False)
    op.create_index(op.f('ix_resume_improvements_recheck_ats_alignment_id'), 'resume_improvements', ['recheck_ats_alignment_id'], unique=False)
    op.create_index(op.f('ix_resume_improvements_user_id'), 'resume_improvements', ['user_id'], unique=False)

    op.add_column('resume_versions', sa.Column('parent_version_id', sa.UUID(), nullable=True))
    op.add_column(
        'resume_versions',
        sa.Column('source', sa.String(length=20), server_default='upload', nullable=False),
    )
    op.alter_column(
        'resume_versions',
        'storage_path',
        existing_type=sa.VARCHAR(length=500),
        nullable=True,
    )
    op.create_index(op.f('ix_resume_versions_parent_version_id'), 'resume_versions', ['parent_version_id'], unique=False)
    op.create_foreign_key(
        RESUME_VERSION_PARENT_FK,
        'resume_versions',
        'resume_versions',
        ['parent_version_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Generated versions have no `storage_path` to restore, so they
    # cannot survive re-applying the NOT NULL constraint. Remove them
    # (and, by FK cascade, the improvement rows referencing them) rather
    # than fabricating a file path that points at nothing. Uploaded
    # versions are untouched.
    op.execute("DELETE FROM resume_versions WHERE storage_path IS NULL")

    op.drop_constraint(RESUME_VERSION_PARENT_FK, 'resume_versions', type_='foreignkey')
    op.drop_index(op.f('ix_resume_versions_parent_version_id'), table_name='resume_versions')
    op.alter_column(
        'resume_versions',
        'storage_path',
        existing_type=sa.VARCHAR(length=500),
        nullable=False,
    )
    op.drop_column('resume_versions', 'source')
    op.drop_column('resume_versions', 'parent_version_id')

    op.drop_index(op.f('ix_resume_improvements_user_id'), table_name='resume_improvements')
    op.drop_index(op.f('ix_resume_improvements_recheck_ats_alignment_id'), table_name='resume_improvements')
    op.drop_index(op.f('ix_resume_improvements_parent_resume_version_id'), table_name='resume_improvements')
    op.drop_index(op.f('ix_resume_improvements_job_id'), table_name='resume_improvements')
    op.drop_index(op.f('ix_resume_improvements_gap_analysis_id'), table_name='resume_improvements')
    op.drop_index(op.f('ix_resume_improvements_child_resume_version_id'), table_name='resume_improvements')
    op.drop_index(op.f('ix_resume_improvements_baseline_ats_alignment_id'), table_name='resume_improvements')
    op.drop_index(op.f('ix_resume_improvements_approval_fingerprint'), table_name='resume_improvements')
    op.drop_table('resume_improvements')
