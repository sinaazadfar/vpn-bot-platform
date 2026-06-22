"""seller bot ui profile

Revision ID: 0019_seller_bot_ui_profile
Revises: 0018_seller_bot_volume_default_zero
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_seller_bot_ui_profile"
down_revision = "0018_seller_bot_volume_default_zero"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "seller_bots",
        sa.Column(
            "ui_profile",
            sa.String(length=32),
            nullable=False,
            server_default="platform",
        ),
    )


def downgrade() -> None:
    op.drop_column("seller_bots", "ui_profile")
