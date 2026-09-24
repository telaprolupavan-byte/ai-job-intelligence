"""add general resume intelligence

Revision ID: a27c0e5b9d13
Revises: 5e3a9c1d7f24
Create Date: 2026-09-24 12:00:00.000000

AJI-027 (General Resume Intelligence). Two new tables, nothing else:

1. `general_resume_assessments` - the insert-only, job-independent General
   Resume Score assessment of one resume version. Its unique constraint
   on `(user_id, resume_version_id, analyzer_version, scoring_version,
   prompt_version)` makes assessment idempotent in the database itself.
2. `general_resume_reviews` - one approve/reject decision set over an
   assessment, the (optional) child version it produced, and that child's
   recheck. `(user_id, assessment_id, approval_fingerprint)` is unique so
   a duplicate submission can never create a second version.

No existing table is altered. `resume_versions.source` gains the value
"general_improvement", which fits the existing String(20) column (there
is no check constraint to change).

Downgrade: dropping the tables alone would leave "general_improvement"
versions behind with no record of how they were produced; those versions
have no stored file either. They are removed with the tables. Uploaded
and AJI-021 versions are never touched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a27c0e5b9d13'
down_revision: Union[str, Sequence[str], None] = '5e3a9c1d7f24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'general_resume_assessments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('resume_version_id', sa.UUID(), nullable=False),
        sa.Column('content_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('analysis_version', sa.String(length=50), nullable=False),
        sa.Column('analyzer_version', sa.String(length=50), nullable=False),
        sa.Column('scoring_version', sa.String(length=50), nullable=False),
        sa.Column('prompt_version', sa.String(length=50), nullable=False),
        sa.Column('model_provider', sa.String(length=100), nullable=True),
        sa.Column('model_name', sa.String(length=150), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('generation_status', sa.String(length=20), nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['resume_version_id'], ['resume_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id',
            'resume_version_id',
            'analyzer_version',
            'scoring_version',
            'prompt_version',
            name='uq_general_resume_assessment_version_pipeline',
        ),
    )
    op.create_index(op.f('ix_general_resume_assessments_resume_version_id'), 'general_resume_assessments', ['resume_version_id'], unique=False)
    op.create_index(op.f('ix_general_resume_assessments_user_id'), 'general_resume_assessments', ['user_id'], unique=False)

    op.create_table(
        'general_resume_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('parent_resume_version_id', sa.UUID(), nullable=False),
        sa.Column('child_resume_version_id', sa.UUID(), nullable=True),
        sa.Column('approval_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('engine_version', sa.String(length=50), nullable=False),
        sa.Column('approved_count', sa.Integer(), nullable=False),
        sa.Column('rejected_count', sa.Integer(), nullable=False),
        sa.Column('decisions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('recheck_status', sa.String(length=20), nullable=False),
        sa.Column('recheck_error', sa.Text(), nullable=True),
        sa.Column('recheck_assessment_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['general_resume_assessments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['child_resume_version_id'], ['resume_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parent_resume_version_id'], ['resume_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recheck_assessment_id'], ['general_resume_assessments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id',
            'assessment_id',
            'approval_fingerprint',
            name='uq_general_resume_review_user_assessment_fingerprint',
        ),
    )
    op.create_index(op.f('ix_general_resume_reviews_approval_fingerprint'), 'general_resume_reviews', ['approval_fingerprint'], unique=False)
    op.create_index(op.f('ix_general_resume_reviews_assessment_id'), 'general_resume_reviews', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_general_resume_reviews_child_resume_version_id'), 'general_resume_reviews', ['child_resume_version_id'], unique=False)
    op.create_index(op.f('ix_general_resume_reviews_parent_resume_version_id'), 'general_resume_reviews', ['parent_resume_version_id'], unique=False)
    op.create_index(op.f('ix_general_resume_reviews_recheck_assessment_id'), 'general_resume_reviews', ['recheck_assessment_id'], unique=False)
    op.create_index(op.f('ix_general_resume_reviews_user_id'), 'general_resume_reviews', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_general_resume_reviews_user_id'), table_name='general_resume_reviews')
    op.drop_index(op.f('ix_general_resume_reviews_recheck_assessment_id'), table_name='general_resume_reviews')
    op.drop_index(op.f('ix_general_resume_reviews_parent_resume_version_id'), table_name='general_resume_reviews')
    op.drop_index(op.f('ix_general_resume_reviews_child_resume_version_id'), table_name='general_resume_reviews')
    op.drop_index(op.f('ix_general_resume_reviews_assessment_id'), table_name='general_resume_reviews')
    op.drop_index(op.f('ix_general_resume_reviews_approval_fingerprint'), table_name='general_resume_reviews')
    op.drop_table('general_resume_reviews')

    op.drop_index(op.f('ix_general_resume_assessments_user_id'), table_name='general_resume_assessments')
    op.drop_index(op.f('ix_general_resume_assessments_resume_version_id'), table_name='general_resume_assessments')
    op.drop_table('general_resume_assessments')

    op.execute(
        "DELETE FROM resume_versions WHERE source = 'general_improvement'"
    )
