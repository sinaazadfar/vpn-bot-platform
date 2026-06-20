"""seller bot volume default zero

Revision ID: 0018_seller_bot_volume_default_zero
Revises: 0017_seller_bot_sales_scope
Create Date: 2026-06-19
"""

from alembic import op


revision = "0018_seller_bot_volume_default_zero"
down_revision = "0017_seller_bot_sales_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE seller_bots SET volume_limit_gb = 0 WHERE volume_limit_gb IS NULL")


def downgrade() -> None:
    pass
