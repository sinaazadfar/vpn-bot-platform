"""seller bot volume limit

Revision ID: 0016_seller_bot_volume_limit
Revises: 0015_payment_rejection_reason
Create Date: 2026-06-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_seller_bot_volume_limit"
down_revision = "0015_payment_rejection_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("seller_bots", sa.Column("volume_limit_gb", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("seller_bots", "volume_limit_gb")
