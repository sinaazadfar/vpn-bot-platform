"""broadcasts

Revision ID: 0007_broadcasts
Revises: 0006_tickets
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_broadcasts"
down_revision = "0006_tickets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_broadcasts_reseller_id"), "broadcasts", ["reseller_id"])
    op.create_table(
        "broadcast_recipients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("broadcast_id", sa.String(length=36), nullable=False),
        sa.Column("buyer_id", sa.String(length=36), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["broadcast_id"], ["broadcasts.id"]),
        sa.ForeignKeyConstraint(["buyer_id"], ["buyers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_broadcast_recipients_broadcast_id"), "broadcast_recipients", ["broadcast_id"])
    op.create_index(op.f("ix_broadcast_recipients_buyer_id"), "broadcast_recipients", ["buyer_id"])
    op.create_index(op.f("ix_broadcast_recipients_telegram_user_id"), "broadcast_recipients", ["telegram_user_id"])
    op.create_index(
        "ix_broadcast_recipients_broadcast_buyer",
        "broadcast_recipients",
        ["broadcast_id", "buyer_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_broadcast_recipients_broadcast_buyer", table_name="broadcast_recipients")
    op.drop_index(op.f("ix_broadcast_recipients_telegram_user_id"), table_name="broadcast_recipients")
    op.drop_index(op.f("ix_broadcast_recipients_buyer_id"), table_name="broadcast_recipients")
    op.drop_index(op.f("ix_broadcast_recipients_broadcast_id"), table_name="broadcast_recipients")
    op.drop_table("broadcast_recipients")
    op.drop_index(op.f("ix_broadcasts_reseller_id"), table_name="broadcasts")
    op.drop_table("broadcasts")

