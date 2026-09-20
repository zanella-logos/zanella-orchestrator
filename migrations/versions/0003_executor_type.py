"""Add process executor type while preserving existing Python robots."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "robots",
        sa.Column("executor_type", sa.String(24), nullable=False, server_default="python"),
    )


def downgrade():
    op.drop_column("robots", "executor_type")
