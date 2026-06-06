"""tickets

Revision ID: 0006_tickets
Revises: 0005_trial_grants
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_tickets"
down_revision = "0005_trial_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reseller_id", sa.String(length=36), nullable=False),
        sa.Column("buyer_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["buyer_id"], ["buyers.id"]),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tickets_reseller_id"), "tickets", ["reseller_id"])
    op.create_index(op.f("ix_tickets_buyer_id"), "tickets", ["buyer_id"])
    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("sender_type", sa.String(length=24), nullable=False),
        sa.Column("sender_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ticket_messages_ticket_id"), "ticket_messages", ["ticket_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ticket_messages_ticket_id"), table_name="ticket_messages")
    op.drop_table("ticket_messages")
    op.drop_index(op.f("ix_tickets_buyer_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_reseller_id"), table_name="tickets")
    op.drop_table("tickets")

