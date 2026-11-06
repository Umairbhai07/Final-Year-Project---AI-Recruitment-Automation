"""Candidate profiles, hard job requirements, profile checks, device lock, answers scored later, email check.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("headline", sa.String(120)),
        sa.Column("phone", sa.String(30)),
        sa.Column("city", sa.String(80)),
        sa.Column("about", sa.Text()),
        sa.Column("photo_key", sa.String(500)),
        sa.Column("highest_degree", sa.String(20)),
        sa.Column("field_of_study", sa.String(120)),
        sa.Column("institute", sa.String(160)),
        sa.Column("cgpa", sa.Float()),
        sa.Column("graduation_year", sa.Integer()),
        sa.Column("experience_years", sa.Float()),
        sa.Column("experience", sa.JSON()),
        sa.Column("skills", sa.JSON()),
        sa.Column("linkedin_url", sa.String(300)),
        sa.Column("github_url", sa.String(300)),
        sa.Column("portfolio_url", sa.String(300)),
        sa.Column("resume_key", sa.String(500)),
        sa.Column("resume_filename", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("users") as batch:
        # accounts that already exist are treated as verified
        batch.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()))
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("min_cgpa", sa.Float(), nullable=True))
        batch.add_column(sa.Column("blocked_applications", sa.Integer(), nullable=False, server_default="0"))
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("profile_snapshot", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("mismatches", sa.JSON(), nullable=True))
    with op.batch_alter_table("interview_sessions") as batch:
        batch.add_column(sa.Column("device_token_hash", sa.String(128), nullable=True))
    with op.batch_alter_table("interview_responses") as batch:
        batch.add_column(sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("interview_responses") as batch:
        batch.drop_column("pending")
    with op.batch_alter_table("interview_sessions") as batch:
        batch.drop_column("device_token_hash")
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("mismatches")
        batch.drop_column("profile_snapshot")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("blocked_applications")
        batch.drop_column("min_cgpa")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified")
    op.drop_table("candidate_profiles")
