"""seller bot volume default zero

Revision ID: 0018_seller_bot_volume_default_zero
Revises: 0017_seller_bot_sales_scope
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_seller_bot_volume_default_zero"
down_revision = "0017_seller_bot_sales_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
        )
    op.execute("UPDATE seller_bots SET volume_limit_gb = 0 WHERE volume_limit_gb IS NULL")


def downgrade() -> None:
    pass
