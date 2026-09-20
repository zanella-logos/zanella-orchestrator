"""Execution log, result, and process details."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("runs", sa.Column("business_summary", sa.Text()))
    op.add_column("runs", sa.Column("stdout_path", sa.Text()))
    op.add_column("runs", sa.Column("stderr_path", sa.Text()))
    op.add_column("runs", sa.Column("result_path", sa.Text()))
    op.add_column("runs", sa.Column("process_id", sa.Integer()))


def downgrade():
    op.drop_column("runs", "process_id")
    op.drop_column("runs", "result_path")
    op.drop_column("runs", "stderr_path")
    op.drop_column("runs", "stdout_path")
    op.drop_column("runs", "business_summary")
