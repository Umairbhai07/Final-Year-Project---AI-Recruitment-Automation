"""Webcam proctoring (setting on jobs, snapshots on sessions) and recruiter "seen" time for New badges.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("require_webcam", sa.Boolean(), nullable=False, server_default=sa.true()))
    with op.batch_alter_table("interview_sessions") as batch:
        batch.add_column(sa.Column("snapshots", sa.JSON(), nullable=True))
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("recruiter_viewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("recruiter_viewed_at")
    with op.batch_alter_table("interview_sessions") as batch:
        batch.drop_column("snapshots")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("require_webcam")
