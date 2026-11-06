"""Interview integrity: thinking time and follow-up questions on jobs; lockdown events and timing on sessions.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("think_seconds", sa.Integer(), nullable=False, server_default="15"))
        batch.add_column(sa.Column("follow_up_questions", sa.Integer(), nullable=False, server_default="1"))
    with op.batch_alter_table("interview_sessions") as batch:
        batch.add_column(sa.Column("integrity_events", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("question_served_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("terminated", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("terminated_reason", sa.String(300), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("interview_sessions") as batch:
        for col in ("terminated_reason", "terminated", "question_served_at", "integrity_events"):
            batch.drop_column(col)
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("follow_up_questions")
        batch.drop_column("think_seconds")
