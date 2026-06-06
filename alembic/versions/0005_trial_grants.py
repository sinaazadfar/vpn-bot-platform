"""trial grants

Revision ID: 0005_trial_grants
Revises: 0004_discount_codes
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_trial_grants"
down_revision = "0004_discount_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trial_grants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("buyer_id", sa.String(length=36), nullable=False),
        sa.Column("vpn_service_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["buyer_id"], ["buyers.id"]),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.ForeignKeyConstraint(["vpn_service_id"], ["vpn_services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trial_grants_reseller_id"), "trial_grants", ["reseller_id"])
    op.create_index(op.f("ix_trial_grants_buyer_id"), "trial_grants", ["buyer_id"])
    op.create_index(
        "ix_trial_grants_reseller_buyer",
        "trial_grants",
        ["reseller_id", "buyer_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_trial_grants_reseller_buyer", table_name="trial_grants")
    op.drop_index(op.f("ix_trial_grants_buyer_id"), table_name="trial_grants")
    op.drop_index(op.f("ix_trial_grants_reseller_id"), table_name="trial_grants")
    op.drop_table("trial_grants")

