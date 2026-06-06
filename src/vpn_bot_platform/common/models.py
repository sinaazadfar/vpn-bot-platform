from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vpn_bot_platform.common.db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def uuid_str() -> str:
    return str(uuid.uuid4())


class UserRole(StrEnum):
    SUPER_USER = "super_user"
    RESELLER_ADMIN = "reseller_admin"
    BUYER = "buyer"


class ResellerStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"


class SellerBotStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    DISABLED = "disabled"
    ERROR = "error"


class PlanScope(StrEnum):
    GLOBAL = "global"
    RESELLER = "reseller"


class OrderStatus(StrEnum):
    DRAFT = "draft"
    WAITING_PAYMENT = "waiting_payment"
    WAITING_APPROVAL = "waiting_approval"
    PROVISIONING = "provisioning"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"


class OrderType(StrEnum):
    NEW_SERVICE = "new_service"
    RENEWAL = "renewal"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFUNDED = "refunded"


class WalletOwnerType(StrEnum):
    BUYER = "buyer"
    RESELLER = "reseller"


class WalletTransactionType(StrEnum):
    CHARGE_REQUEST = "charge_request"
    CHARGE_APPROVED = "charge_approved"
    PURCHASE_DEBIT = "purchase_debit"
    RESELLER_CREDIT = "reseller_credit"


class WalletTransactionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    REJECTED = "rejected"


class DiscountType(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"


class TicketStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class TicketMessageSenderType(StrEnum):
    BUYER = "buyer"
    ADMIN = "admin"


class BroadcastStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"


class SettingScope(StrEnum):
    GLOBAL = "global"
    RESELLER = "reseller"


class AuditActorType(StrEnum):
    SUPER_USER = "super_user"
    RESELLER_ADMIN = "reseller_admin"
    BUYER = "buyer"
    SYSTEM = "system"


class PaymentGatewayStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Reseller(Base):
    __tablename__ = "resellers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    telegram_user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default=ResellerStatus.ACTIVE.value)
    wallet_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    telegram_user: Mapped[TelegramUser] = relationship()


class SellerBot(Base):
    __tablename__ = "seller_bots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    token_encrypted: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default=SellerBotStatus.PENDING.value)
    container_name: Mapped[str | None] = mapped_column(String(128))
    container_id: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    reseller: Mapped[Reseller] = relationship()


class MarzbanPanel(Base):
    __tablename__ = "marzban_panels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str] = mapped_column(String(255), unique=True)
    username_encrypted: Mapped[str | None] = mapped_column(Text)
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    token_encrypted: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResellerPanelAssignment(Base):
    __tablename__ = "reseller_panel_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("marzban_panels.id"), index=True)
    marzban_admin_username: Mapped[str | None] = mapped_column(String(128))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (Index("ix_plans_reseller_scope", "reseller_id", "scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str | None] = mapped_column(ForeignKey("resellers.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(16), default=PlanScope.GLOBAL.value)
    name: Mapped[str] = mapped_column(String(128))
    price: Mapped[float] = mapped_column(Numeric(18, 2))
    duration_days: Mapped[int] = mapped_column(Integer)
    data_limit_gb: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Buyer(Base):
    __tablename__ = "buyers"
    __table_args__ = (Index("ix_buyers_reseller_tg", "reseller_id", "telegram_user_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    telegram_user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True)
    wallet_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), index=True)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id"))
    target_service_id: Mapped[str | None] = mapped_column(ForeignKey("vpn_services.id"))
    order_type: Mapped[str] = mapped_column(String(32), default=OrderType.NEW_SERVICE.value)
    status: Mapped[str] = mapped_column(String(32), default=OrderStatus.DRAFT.value)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default=PaymentStatus.PENDING.value)
    method: Mapped[str] = mapped_column(String(32), default="card_to_card")
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    proof_file_id: Mapped[str | None] = mapped_column(String(255))
    approved_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VpnService(Base):
    __tablename__ = "vpn_services"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), index=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("marzban_panels.id"), index=True)
    marzban_username: Mapped[str] = mapped_column(String(128), index=True)
    subscription_url: Mapped[str | None] = mapped_column(Text)
    data_limit_gb: Mapped[int | None] = mapped_column(Integer)
    expire_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (Index("ix_wallet_transactions_owner", "owner_type", "owner_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    owner_type: Mapped[str] = mapped_column(String(24))
    owner_id: Mapped[str] = mapped_column(String(36))
    transaction_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default=WalletTransactionStatus.COMPLETED.value)
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    note: Mapped[str | None] = mapped_column(Text)
    related_payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.id"))
    approved_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiscountCode(Base):
    __tablename__ = "discount_codes"
    __table_args__ = (Index("ix_discount_codes_reseller_code", "reseller_id", "code", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str | None] = mapped_column(ForeignKey("resellers.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(64))
    discount_type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    max_uses: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrialGrant(Base):
    __tablename__ = "trial_grants"
    __table_args__ = (Index("ix_trial_grants_reseller_buyer", "reseller_id", "buyer_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), index=True)
    vpn_service_id: Mapped[str | None] = mapped_column(ForeignKey("vpn_services.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str] = mapped_column(ForeignKey("resellers.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), index=True)
    subject: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default=TicketStatus.OPEN.value)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    sender_type: Mapped[str] = mapped_column(String(24))
    sender_telegram_id: Mapped[int] = mapped_column(BigInteger)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str | None] = mapped_column(ForeignKey("resellers.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=BroadcastStatus.DRAFT.value)
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_telegram_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (Index("ix_broadcast_recipients_broadcast_buyer", "broadcast_id", "buyer_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    broadcast_id: Mapped[str] = mapped_column(ForeignKey("broadcasts.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class PlatformSetting(Base):
    __tablename__ = "platform_settings"
    __table_args__ = (Index("ix_platform_settings_scope_key", "scope", "scope_id", "key", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    scope: Mapped[str] = mapped_column(String(24))
    scope_id: Mapped[str | None] = mapped_column(String(36))
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor", "actor_type", "actor_telegram_id"),
        Index("ix_audit_logs_reseller_action", "reseller_id", "action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    reseller_id: Mapped[str | None] = mapped_column(ForeignKey("resellers.id"), index=True)
    action: Mapped[str] = mapped_column(String(96), index=True)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (Index("ix_rate_limit_buckets_identity", "scope", "identity", "bucket_key", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    scope: Mapped[str] = mapped_column(String(32))
    identity: Mapped[str] = mapped_column(String(128))
    bucket_key: Mapped[str] = mapped_column(String(80))
    count: Mapped[int] = mapped_column(Integer, default=0)
    reset_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class PaymentGateway(Base):
    __tablename__ = "payment_gateways"
    __table_args__ = (Index("ix_payment_gateways_scope_provider", "reseller_id", "provider", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reseller_id: Mapped[str | None] = mapped_column(ForeignKey("resellers.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(24), default=PaymentGatewayStatus.ACTIVE.value)
    config_encrypted: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
