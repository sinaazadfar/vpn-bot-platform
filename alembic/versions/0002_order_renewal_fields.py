"""order renewal fields

Revision ID: 0002_order_renewal_fields
Revises: 0001_initial_platform_schema
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_order_renewal_fields"
down_revision = "0001_initial_platform_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("target_service_id", sa.String(length=36), nullable=True))
    op.add_column(
        "orders",
        sa.Column("order_type", sa.String(length=32), nullable=False, server_default="new_service"),
    )
    op.create_foreign_key(
        "fk_orders_target_service_id_vpn_services",
        "orders",
        "vpn_services",
        ["target_service_id"],
        ["id"],
    )
    op.alter_column("orders", "order_type", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_orders_target_service_id_vpn_services", "orders", type_="foreignkey")
    op.drop_column("orders", "order_type")
    op.drop_column("orders", "target_service_id")

