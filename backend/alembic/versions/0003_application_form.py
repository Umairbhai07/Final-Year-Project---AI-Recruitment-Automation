"""Application form: questions on jobs, answers on applications.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op
from app.schemas.form import DEFAULT_FORM

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("application_form", sa.JSON(), nullable=True))
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("form_answers", sa.JSON(), nullable=True))
    # existing jobs get the default form, so nothing changes for jobs that were already posted
    jobs = sa.table("jobs", sa.column("application_form", sa.JSON()))
    op.execute(jobs.update().values(application_form=DEFAULT_FORM))


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("form_answers")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("application_form")
