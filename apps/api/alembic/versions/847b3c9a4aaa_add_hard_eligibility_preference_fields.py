"""add hard eligibility preference fields

Revision ID: 847b3c9a4aaa
Revises: c8e7007f5d4a
Create Date: 2026-09-17 14:21:13.692028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '847b3c9a4aaa'
down_revision: Union[str, Sequence[str], None] = 'c8e7007f5d4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # AJI-011 Hard Eligibility Engine: new nullable Preference fields.
    # All are nullable (None = "unspecified", the hard check for that
    # constraint is skipped) except enforce_minimum_experience, which
    # defaults to False so existing rows keep today's behavior
    # (experience never becomes a hard filter unless a user opts in).
    op.add_column(
        'preferences',
        sa.Column(
            'excluded_locations',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        'preferences',
        sa.Column('requires_sponsorship', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'preferences',
        sa.Column('is_us_citizen', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'preferences',
        sa.Column('has_security_clearance', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'preferences',
        sa.Column(
            'enforce_minimum_experience',
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('preferences', 'enforce_minimum_experience')
    op.drop_column('preferences', 'has_security_clearance')
    op.drop_column('preferences', 'is_us_citizen')
    op.drop_column('preferences', 'requires_sponsorship')
    op.drop_column('preferences', 'excluded_locations')
