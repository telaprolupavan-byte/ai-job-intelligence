"""add resume version file storage and content fingerprint

Revision ID: 12c6df217e08
Revises: 4c4bbebf2376
Create Date: 2026-09-17 05:00:00.000000

"""
import hashlib
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12c6df217e08'
down_revision: Union[str, Sequence[str], None] = '4c4bbebf2376'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _fingerprint(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def upgrade() -> None:
    """Upgrade schema.

    Physical resume files and content fingerprints move from `resumes`
    (one file per Resume) to `resume_versions` (one file per version),
    since each version is now a distinct upload with its own content.
    Existing rows are backfilled from their parent Resume, since every
    pre-existing Resume has exactly one ("Original") version.
    """
    op.add_column(
        'resume_versions',
        sa.Column('content_fingerprint', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'resume_versions',
        sa.Column('original_filename', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'resume_versions',
        sa.Column('storage_path', sa.String(length=500), nullable=True),
    )

    bind = op.get_bind()

    rows = bind.execute(
        sa.text(
            """
            SELECT rv.id, rv.content_text, r.filename, r.storage_path
            FROM resume_versions rv
            JOIN resumes r ON r.id = rv.resume_id
            """
        )
    ).fetchall()

    for version_id, content_text, filename, storage_path in rows:
        bind.execute(
            sa.text(
                """
                UPDATE resume_versions
                SET content_fingerprint = :fingerprint,
                    original_filename = :filename,
                    storage_path = :storage_path
                WHERE id = :id
                """
            ),
            {
                "fingerprint": _fingerprint(content_text),
                "filename": filename,
                "storage_path": storage_path or "",
                "id": version_id,
            },
        )

    op.alter_column('resume_versions', 'content_fingerprint', nullable=False)
    op.alter_column('resume_versions', 'original_filename', nullable=False)
    op.alter_column('resume_versions', 'storage_path', nullable=False)

    op.create_index(
        op.f('ix_resume_versions_content_fingerprint'),
        'resume_versions',
        ['content_fingerprint'],
        unique=False,
    )

    op.drop_column('resumes', 'storage_path')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'resumes',
        sa.Column('storage_path', sa.String(length=500), nullable=True),
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE resumes r
            SET storage_path = rv.storage_path
            FROM resume_versions rv
            WHERE rv.resume_id = r.id
            """
        )
    )

    op.drop_index(
        op.f('ix_resume_versions_content_fingerprint'),
        table_name='resume_versions',
    )
    op.drop_column('resume_versions', 'storage_path')
    op.drop_column('resume_versions', 'original_filename')
    op.drop_column('resume_versions', 'content_fingerprint')
