"""add requirement intelligence reference to ats alignment results

Revision ID: c3f6a1d47e21
Revises: 8a040c819900
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3f6a1d47e21'
down_revision: Union[str, Sequence[str], None] = '8a040c819900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'ats_alignment_results',
        sa.Column('requirement_intelligence_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'ats_alignment_results',
        sa.Column(
            'requirement_intelligence_fingerprint',
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.create_index(
        op.f('ix_ats_alignment_results_requirement_intelligence_id'),
        'ats_alignment_results',
        ['requirement_intelligence_id'],
        unique=False,
    )
    op.create_foreign_key(
        'ats_alignment_results_requirement_intelligence_id_fkey',
        'ats_alignment_results',
        'requirement_intelligence',
        ['requirement_intelligence_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ats_alignment_results_requirement_intelligence_id_fkey',
        'ats_alignment_results',
        type_='foreignkey',
    )
    op.drop_index(
        op.f('ix_ats_alignment_results_requirement_intelligence_id'),
        table_name='ats_alignment_results',
    )
    op.drop_column('ats_alignment_results', 'requirement_intelligence_fingerprint')
    op.drop_column('ats_alignment_results', 'requirement_intelligence_id')
