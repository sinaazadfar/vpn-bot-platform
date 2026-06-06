from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_hardening_controls"
down_revision = "0008_platform_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reseller_panel_assignments", sa.Column("priority", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("reseller_panel_assignments", sa.Column("weight", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("reseller_panel_assignments", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("reseller_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=96), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_type", "actor_telegram_id"])
    op.create_index("ix_audit_logs_reseller_action", "audit_logs", ["reseller_id", "action"])
    op.create_index("ix_audit_logs_reseller_id", "audit_logs", ["reseller_id"])

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("identity", sa.String(length=128), nullable=False),
        sa.Column("bucket_key", sa.String(length=80), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rate_limit_buckets_identity",
        "rate_limit_buckets",
        ["scope", "identity", "bucket_key"],
        unique=True,
    )

    op.create_table(
        "payment_gateways",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("config_encrypted", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_gateways_reseller_id", "payment_gateways", ["reseller_id"])
    op.create_index(
        "ix_payment_gateways_scope_provider",
        "payment_gateways",
        ["reseller_id", "provider"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_gateways_scope_provider", table_name="payment_gateways")
    op.drop_index("ix_payment_gateways_reseller_id", table_name="payment_gateways")
    op.drop_table("payment_gateways")
    op.drop_index("ix_rate_limit_buckets_identity", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
    op.drop_index("ix_audit_logs_reseller_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_reseller_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_column("reseller_panel_assignments", "is_active")
    op.drop_column("reseller_panel_assignments", "weight")
    op.drop_column("reseller_panel_assignments", "priority")
