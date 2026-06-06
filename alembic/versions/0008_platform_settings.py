"""platform settings

Revision ID: 0008_platform_settings
Revises: 0007_broadcasts
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_platform_settings"
down_revision = "0007_broadcasts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("scope_id", sa.String(length=36), nullable=True),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_settings_scope_key",
        "platform_settings",
        ["scope", "scope_id", "key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_platform_settings_scope_key", table_name="platform_settings")
    op.drop_table("platform_settings")

