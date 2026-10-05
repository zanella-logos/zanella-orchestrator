"""Allow unlimited executions without changing existing limits or history."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("robots", table_args=[sa.CheckConstraint("timeout > 0", name="ck_robots_timeout_positive")]) as batch:
        batch.alter_column("timeout", existing_type=sa.Float(), nullable=True)


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM robots WHERE timeout IS NULL")):
        raise RuntimeError("Unlimited executions must be given an explicit limit before downgrading.")
    with op.batch_alter_table("robots") as batch:
        batch.alter_column("timeout", existing_type=sa.Float(), nullable=False)
