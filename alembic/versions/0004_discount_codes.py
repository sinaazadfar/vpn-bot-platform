"""discount codes

Revision ID: 0004_discount_codes
Revises: 0003_wallet_transactions
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_discount_codes"
down_revision = "0003_wallet_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discount_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("discount_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_discount_codes_reseller_code",
        "discount_codes",
        ["reseller_id", "code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_discount_codes_reseller_code", table_name="discount_codes")
    op.drop_table("discount_codes")

