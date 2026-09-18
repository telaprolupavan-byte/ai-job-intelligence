"""add requirement intelligence

Revision ID: 8a040c819900
Revises: 6fdd95443549
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8a040c819900'
down_revision: Union[str, Sequence[str], None] = '6fdd95443549'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('requirement_intelligence',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('content_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('raw_jd_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('analysis_version', sa.String(length=50), nullable=False),
    sa.Column('analyzer_version', sa.String(length=50), nullable=False),
    sa.Column('prompt_version', sa.String(length=50), nullable=False),
    sa.Column('model_provider', sa.String(length=100), nullable=True),
    sa.Column('model_name', sa.String(length=150), nullable=True),
    sa.Column('extraction_status', sa.String(length=20), nullable=False),
    sa.Column('structured_intelligence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint(
        'user_id', 'job_id', 'content_fingerprint', 'analyzer_version',
        'prompt_version', 'model_provider', 'model_name',
        name='uq_requirement_intelligence_identity',
    ),
    )
    op.create_index(op.f('ix_requirement_intelligence_content_fingerprint'), 'requirement_intelligence', ['content_fingerprint'], unique=False)
    op.create_index(op.f('ix_requirement_intelligence_job_id'), 'requirement_intelligence', ['job_id'], unique=False)
    op.create_index(op.f('ix_requirement_intelligence_user_id'), 'requirement_intelligence', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_requirement_intelligence_user_id'), table_name='requirement_intelligence')
    op.drop_index(op.f('ix_requirement_intelligence_job_id'), table_name='requirement_intelligence')
    op.drop_index(op.f('ix_requirement_intelligence_content_fingerprint'), table_name='requirement_intelligence')
    op.drop_table('requirement_intelligence')
