"""remove legacy job_match resume_analysis resume_recommendation search_run tables

AJI-009 foundation cleanup: JobMatch, ResumeAnalysis, ResumeRecommendation, and
SearchRun were dead legacy models from the initial schema with zero references
anywhere in the current application (routers, services, tests). They were
superseded by JobMatchResult and ResumeAIAnalysis respectively. SavedJob is
intentionally NOT touched here; it remains reserved for future application
tracking work.

Revision ID: c8e7007f5d4a
Revises: 12c6df217e08
Create Date: 2026-09-17 07:21:40.721062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c8e7007f5d4a'
down_revision: Union[str, Sequence[str], None] = '12c6df217e08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('resume_recommendations')
    op.drop_table('resume_analyses')
    op.drop_table('job_matches')
    op.drop_table('search_runs')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        'search_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('jobs_found', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'job_matches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('resume_version_id', sa.UUID(), nullable=True),
        sa.Column('match_score', sa.Float(), nullable=False),
        sa.Column('ats_score', sa.Float(), nullable=False),
        sa.Column('priority', sa.String(length=50), nullable=True),
        sa.Column('explanation', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resume_version_id'], ['resume_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'resume_analyses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('resume_version_id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=True),
        sa.Column('ats_score', sa.Float(), nullable=False),
        sa.Column('keyword_alignment', sa.Float(), nullable=True),
        sa.Column('requirement_coverage', sa.Float(), nullable=True),
        sa.Column('structure_score', sa.Float(), nullable=True),
        sa.Column('title_alignment', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resume_version_id'], ['resume_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'resume_recommendations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('resume_version_id', sa.UUID(), nullable=False),
        sa.Column('recommendation_type', sa.String(length=100), nullable=False),
        sa.Column('original_text', sa.Text(), nullable=True),
        sa.Column('suggested_text', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resume_version_id'], ['resume_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
