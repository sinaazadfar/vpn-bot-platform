from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_plan_purpose_extra_volume"
down_revision = "0010_widen_rate_limit_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("purpose", sa.String(length=24), nullable=True))
    op.execute("UPDATE plans SET purpose = 'purchase' WHERE purpose IS NULL")
    op.alter_column(
        "plans",
        "purpose",
        existing_type=sa.String(length=24),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("plans", "purpose")
