"""Initial robot and execution schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "robots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("script", sa.Text(), nullable=False),
        sa.Column("interpreter", sa.Text(), nullable=False),
        sa.Column("cwd", sa.Text(), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("timeout", sa.Float(), nullable=False),
        sa.CheckConstraint("timeout > 0"),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("robot_id", sa.String(36), sa.ForeignKey("robots.id"), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("started_at", sa.Float()),
        sa.Column("ended_at", sa.Float()),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("business_result", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text()),
    )
    op.create_index("ix_runs_state", "runs", ["state"])


def downgrade():
    op.drop_table("runs")
    op.drop_table("robots")
