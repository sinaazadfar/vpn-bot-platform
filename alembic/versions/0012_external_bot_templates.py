from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_external_bot_templates"
down_revision = "0011_plan_purpose_extra_volume"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_bot_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("repo_url", sa.String(length=512), nullable=False),
        sa.Column("ref", sa.String(length=128), nullable=False),
        sa.Column("local_path", sa.String(length=512), nullable=True),
        sa.Column("license_name", sa.String(length=64), nullable=True),
        sa.Column("runtime_adapter", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_synced_commit", sa.String(length=64), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_external_bot_templates_key"),
        "external_bot_templates",
        ["key"],
        unique=True,
    )

    op.add_column(
        "seller_bots",
        sa.Column("external_template_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "seller_bots",
        sa.Column("runtime_type", sa.String(length=32), nullable=True),
    )
    op.execute("UPDATE seller_bots SET runtime_type = 'native' WHERE runtime_type IS NULL")
    op.alter_column(
        "seller_bots",
        "runtime_type",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.create_index(
        op.f("ix_seller_bots_external_template_id"),
        "seller_bots",
        ["external_template_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_seller_bots_external_template_id",
        "seller_bots",
        "external_bot_templates",
        ["external_template_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_seller_bots_external_template_id",
        "seller_bots",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_seller_bots_external_template_id"), table_name="seller_bots")
    op.drop_column("seller_bots", "runtime_type")
    op.drop_column("seller_bots", "external_template_id")
    op.drop_index(op.f("ix_external_bot_templates_key"), table_name="external_bot_templates")
    op.drop_table("external_bot_templates")
