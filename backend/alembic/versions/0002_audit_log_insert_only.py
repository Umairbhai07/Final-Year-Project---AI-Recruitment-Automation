"""Make ai_audit_log insert-only with a Postgres trigger that raises on UPDATE/DELETE.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ai_audit_log_block_changes() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'ai_audit_log is insert-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER ai_audit_log_no_update_delete
        BEFORE UPDATE OR DELETE ON ai_audit_log
        FOR EACH ROW EXECUTE FUNCTION ai_audit_log_block_changes();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS ai_audit_log_no_update_delete ON ai_audit_log")
    op.execute("DROP FUNCTION IF EXISTS ai_audit_log_block_changes()")
