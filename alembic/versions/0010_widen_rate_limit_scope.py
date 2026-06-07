from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_widen_rate_limit_scope"
down_revision = "0009_hardening_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "rate_limit_buckets",
        "scope",
        existing_type=sa.String(length=32),
        type_=sa.String(length=96),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "rate_limit_buckets",
        "scope",
        existing_type=sa.String(length=96),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
