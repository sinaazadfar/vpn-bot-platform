"""wallet charge receipts

Revision ID: 0014_wallet_charge_receipts
Revises: 0013_order_requested_username
Create Date: 2026-06-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_wallet_charge_receipts"
down_revision = "0013_order_requested_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wallet_transactions", sa.Column("proof_file_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("wallet_transactions", "proof_file_id")
