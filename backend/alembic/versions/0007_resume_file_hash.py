"""Resume file fingerprint, to spot the same resume used by two accounts.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("file_hash", sa.String(64), nullable=True))
    op.create_index("ix_resumes_file_hash", "resumes", ["file_hash"])


def downgrade() -> None:
    op.drop_index("ix_resumes_file_hash", table_name="resumes")
    op.drop_column("resumes", "file_hash")
