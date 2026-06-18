"""payment rejection reason

Revision ID: 0015_payment_rejection_reason
Revises: 0014_wallet_charge_receipts
Create Date: 2026-06-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_payment_rejection_reason"
down_revision = "0014_wallet_charge_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("rejection_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "rejection_reason")
