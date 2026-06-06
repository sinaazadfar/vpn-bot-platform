"""wallet transactions

Revision ID: 0003_wallet_transactions
Revises: 0002_order_renewal_fields
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_wallet_transactions"
down_revision = "0002_order_renewal_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("owner_type", sa.String(length=24), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("related_payment_id", sa.String(length=36), nullable=True),
        sa.Column("approved_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["related_payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wallet_transactions_reseller_id"), "wallet_transactions", ["reseller_id"])
    op.create_index(
        "ix_wallet_transactions_owner",
        "wallet_transactions",
        ["owner_type", "owner_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_transactions_owner", table_name="wallet_transactions")
    op.drop_index(op.f("ix_wallet_transactions_reseller_id"), table_name="wallet_transactions")
    op.drop_table("wallet_transactions")

