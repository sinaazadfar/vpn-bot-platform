"""seller bot sales scope

Revision ID: 0017_seller_bot_sales_scope
Revises: 0016_seller_bot_volume_limit
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_seller_bot_sales_scope"
down_revision = "0016_seller_bot_volume_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("seller_bot_id", sa.String(length=36), nullable=True))
    op.add_column("payments", sa.Column("seller_bot_id", sa.String(length=36), nullable=True))
    op.add_column("vpn_services", sa.Column("seller_bot_id", sa.String(length=36), nullable=True))
    op.add_column("wallet_transactions", sa.Column("seller_bot_id", sa.String(length=36), nullable=True))

    op.create_index(op.f("ix_orders_seller_bot_id"), "orders", ["seller_bot_id"])
    op.create_index(op.f("ix_payments_seller_bot_id"), "payments", ["seller_bot_id"])
    op.create_index(op.f("ix_vpn_services_seller_bot_id"), "vpn_services", ["seller_bot_id"])
    op.create_index(op.f("ix_wallet_transactions_seller_bot_id"), "wallet_transactions", ["seller_bot_id"])

    op.create_foreign_key("fk_orders_seller_bot_id", "orders", "seller_bots", ["seller_bot_id"], ["id"])
    op.create_foreign_key("fk_payments_seller_bot_id", "payments", "seller_bots", ["seller_bot_id"], ["id"])
    op.create_foreign_key("fk_vpn_services_seller_bot_id", "vpn_services", "seller_bots", ["seller_bot_id"], ["id"])
    op.create_foreign_key(
        "fk_wallet_transactions_seller_bot_id",
        "wallet_transactions",
        "seller_bots",
        ["seller_bot_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_wallet_transactions_seller_bot_id", "wallet_transactions", type_="foreignkey")
    op.drop_constraint("fk_vpn_services_seller_bot_id", "vpn_services", type_="foreignkey")
    op.drop_constraint("fk_payments_seller_bot_id", "payments", type_="foreignkey")
    op.drop_constraint("fk_orders_seller_bot_id", "orders", type_="foreignkey")

    op.drop_index(op.f("ix_wallet_transactions_seller_bot_id"), table_name="wallet_transactions")
    op.drop_index(op.f("ix_vpn_services_seller_bot_id"), table_name="vpn_services")
    op.drop_index(op.f("ix_payments_seller_bot_id"), table_name="payments")
    op.drop_index(op.f("ix_orders_seller_bot_id"), table_name="orders")

    op.drop_column("wallet_transactions", "seller_bot_id")
    op.drop_column("vpn_services", "seller_bot_id")
    op.drop_column("payments", "seller_bot_id")
    op.drop_column("orders", "seller_bot_id")
