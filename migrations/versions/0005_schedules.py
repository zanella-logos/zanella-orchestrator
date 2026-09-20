"""Add persistent daily and weekly schedules."""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "robot_id", sa.String(36),
            sa.ForeignKey("robots.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("frequency", sa.String(16), nullable=False),
        sa.Column("time_of_day", sa.String(5), nullable=False),
        sa.Column("weekday", sa.Integer()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.Float(), nullable=False),
        sa.Column("last_run_at", sa.Float()),
    )
    op.create_index("ix_schedules_robot_id", "schedules", ["robot_id"])
    op.create_index("ix_schedules_next_run_at", "schedules", ["next_run_at"])


def downgrade():
    op.drop_table("schedules")
