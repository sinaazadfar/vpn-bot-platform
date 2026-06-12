from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_order_requested_username"
down_revision = "0012_external_bot_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("requested_username", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "requested_username")
