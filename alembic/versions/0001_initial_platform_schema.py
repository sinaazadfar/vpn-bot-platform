"""initial platform schema

Revision ID: 0001_initial_platform_schema
Revises:
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_platform_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "marzban_panels",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("username_encrypted", sa.Text(), nullable=True),
        sa.Column("password_encrypted", sa.Text(), nullable=True),
        sa.Column("token_encrypted", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("base_url"),
    )

    op.create_table(
        "resellers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("wallet_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["telegram_user_id"], ["telegram_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resellers_telegram_user_id"), "resellers", ["telegram_user_id"])

    op.create_table(
        "seller_bots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("container_name", sa.String(length=128), nullable=True),
        sa.Column("container_id", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_seller_bots_reseller_id"), "seller_bots", ["reseller_id"])
    op.create_index(op.f("ix_seller_bots_token_hash"), "seller_bots", ["token_hash"], unique=True)

    op.create_table(
        "reseller_panel_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("panel_id", sa.String(length=36), nullable=False),
        sa.Column("marzban_admin_username", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["panel_id"], ["marzban_panels.id"]),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reseller_panel_assignments_panel_id"),
        "reseller_panel_assignments",
        ["panel_id"],
    )
    op.create_index(
        op.f("ix_reseller_panel_assignments_reseller_id"),
        "reseller_panel_assignments",
        ["reseller_id"],
    )

    op.create_table(
        "plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("data_limit_gb", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plans_reseller_scope", "plans", ["reseller_id", "scope"])

    op.create_table(
        "buyers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("wallet_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.ForeignKeyConstraint(["telegram_user_id"], ["telegram_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_buyers_reseller_tg", "buyers", ["reseller_id", "telegram_user_id"], unique=True)
    op.create_index(op.f("ix_buyers_reseller_id"), "buyers", ["reseller_id"])
    op.create_index(op.f("ix_buyers_telegram_user_id"), "buyers", ["telegram_user_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("buyer_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["buyer_id"], ["buyers.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_buyer_id"), "orders", ["buyer_id"])
    op.create_index(op.f("ix_orders_reseller_id"), "orders", ["reseller_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("proof_file_id", sa.String(length=255), nullable=True),
        sa.Column("approved_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payments_order_id"), "payments", ["order_id"])
    op.create_index(op.f("ix_payments_reseller_id"), "payments", ["reseller_id"])

    op.create_table(
        "vpn_services",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("buyer_id", sa.String(length=36), nullable=False),
        sa.Column("panel_id", sa.String(length=36), nullable=False),
        sa.Column("marzban_username", sa.String(length=128), nullable=False),
        sa.Column("subscription_url", sa.Text(), nullable=True),
        sa.Column("data_limit_gb", sa.Integer(), nullable=True),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["buyer_id"], ["buyers.id"]),
        sa.ForeignKeyConstraint(["panel_id"], ["marzban_panels.id"]),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vpn_services_buyer_id"), "vpn_services", ["buyer_id"])
    op.create_index(op.f("ix_vpn_services_marzban_username"), "vpn_services", ["marzban_username"])
    op.create_index(op.f("ix_vpn_services_panel_id"), "vpn_services", ["panel_id"])
    op.create_index(op.f("ix_vpn_services_reseller_id"), "vpn_services", ["reseller_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_vpn_services_reseller_id"), table_name="vpn_services")
    op.drop_index(op.f("ix_vpn_services_panel_id"), table_name="vpn_services")
    op.drop_index(op.f("ix_vpn_services_marzban_username"), table_name="vpn_services")
    op.drop_index(op.f("ix_vpn_services_buyer_id"), table_name="vpn_services")
    op.drop_table("vpn_services")
    op.drop_index(op.f("ix_payments_reseller_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_order_id"), table_name="payments")
    op.drop_table("payments")
    op.drop_index(op.f("ix_orders_reseller_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_buyer_id"), table_name="orders")
    op.drop_table("orders")
    op.drop_index(op.f("ix_buyers_telegram_user_id"), table_name="buyers")
    op.drop_index(op.f("ix_buyers_reseller_id"), table_name="buyers")
    op.drop_index("ix_buyers_reseller_tg", table_name="buyers")
    op.drop_table("buyers")
    op.drop_index("ix_plans_reseller_scope", table_name="plans")
    op.drop_table("plans")
    op.drop_index(op.f("ix_reseller_panel_assignments_reseller_id"), table_name="reseller_panel_assignments")
    op.drop_index(op.f("ix_reseller_panel_assignments_panel_id"), table_name="reseller_panel_assignments")
    op.drop_table("reseller_panel_assignments")
    op.drop_index(op.f("ix_seller_bots_token_hash"), table_name="seller_bots")
    op.drop_index(op.f("ix_seller_bots_reseller_id"), table_name="seller_bots")
    op.drop_table("seller_bots")
    op.drop_index(op.f("ix_resellers_telegram_user_id"), table_name="resellers")
    op.drop_table("resellers")
    op.drop_table("marzban_panels")
    op.drop_table("telegram_users")
