from __future__ import annotations

import datetime as dt

import pytest
from cryptography.fernet import Fernet

from vpn_bot_platform.common.config import Settings
from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine, session_scope
from vpn_bot_platform.common.models import Buyer, DiscountType, Order, Payment, PlanPurpose, SellerBotUiProfile
from vpn_bot_platform.common.repositories import create_vpn_service
from vpn_bot_platform.integrations.marzban import (
    MarzbanCredentials,
    MarzbanUserCreate,
    MarzbanUserUpdate,
)
from vpn_bot_platform.master_bot.services.resellers import ResellerService
from vpn_bot_platform.seller_bot.provisioning import ProvisioningService, _marzban_username
from vpn_bot_platform.seller_bot.services import SellerContextService
from vpn_bot_platform.seller_bot.handlers import _normalize_service_username, main_kb


class FakeMarzbanClient:
    created_users: list[MarzbanUserCreate] = []
    revoked_users: list[str] = []

    def __init__(self, credentials: MarzbanCredentials) -> None:
        self.credentials = credentials

    async def create_user(self, user: MarzbanUserCreate) -> dict:
        self.created_users.append(user)
        return {
            "username": user.username,
            "subscription_url": f"{self.credentials.base_url}/sub/{user.username}",
        }

    async def update_user(self, username: str, update: MarzbanUserUpdate) -> dict:
        return {"username": username, **update.to_payload()}

    async def get_inbounds(self) -> dict:
        return {
            "vless": [{"tag": "VLESS TCP REALITY"}],
            "vmess": [{"tag": "VMess WS TLS"}],
            "trojan": ["Trojan TCP TLS"],
        }

    async def revoke_user_subscription(self, username: str) -> dict:
        self.revoked_users.append(username)
        return {
            "username": username,
            "subscription_url": f"{self.credentials.base_url}/sub/revoked/{username}",
        }


def test_marzban_username_matches_panel_validation() -> None:
    username = _marzban_username(
        "u",
        "23db27e6-2967-4a10-af2e-abc5030cd3c6",
        252486544,
    )

    assert 3 <= len(username) <= 32
    assert username == username.lower()
    assert username.replace("_", "").isalnum()


def test_requested_service_username_gets_safe_random_suffix() -> None:
    username = _marzban_username(
        "u",
        "23db27e6-2967-4a10-af2e-abc5030cd3c6",
        252486544,
        requested_username="sina_home",
    )

    assert username.startswith("sina_home_")
    assert len(username) <= 32
    assert username == username.lower()
    assert username.replace("_", "").isascii()
    assert username.replace("_", "").isalnum()


def test_service_username_input_validation() -> None:
    assert _normalize_service_username("@Sina_Home") == "sina_home"
    assert _normalize_service_username("ab") is None
    assert _normalize_service_username("نام") is None
    assert _normalize_service_username("bad-name") is None
    assert _normalize_service_username("_bad") is None


def test_buyer_main_menu_has_subscription_layout() -> None:
    labels_by_row = [[button.text for button in row] for row in main_kb().inline_keyboard]
    labels = [label for row in labels_by_row for label in row]

    assert labels_by_row[:6] == [
        ["خرید اشتراک"],
        ["اشتراک‌های من", "جستجو اشتراک"],
        ["حساب کاربری"],
        ["افزایش موجودی"],
        ["کسب درآمد", "آموزش"],
        ["پشتیبانی"],
    ]
    assert "پرداختی‌های من" not in labels
    assert "تمدید سرویس" not in labels


@pytest.mark.asyncio
async def test_admin_price_per_gb_plans_replace_custom_purchase_plans() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    master_service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await master_service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="seller_a_bot",
            bot_token="123:secret",
            volume_limit_gb=500,
        )
        seller_context = SellerContextService(seller_bot.id)
        old_plan = await seller_context.create_admin_plan(
            admin_telegram_id=111,
            name="old custom",
            price=100000,
            duration_days=45,
            data_limit_gb=25,
        )

        created = await seller_context.replace_admin_price_per_gb_plans(
            admin_telegram_id=111,
            volumes_gb=[10, 20],
            monthly_price_per_gb=1000,
            three_month_price_per_gb=2500,
            discount_price_per_gb=2000,
        )
        plans = await seller_context.list_admin_plans(admin_telegram_id=111)
    finally:
        await dispose_engine()

    seller_plans = [plan for plan in plans if plan.reseller_id == seller_bot.reseller_id]
    assert len(created) == 6
    assert old_plan.id not in {plan.id for plan in seller_plans}
    assert {(plan.name, plan.duration_days, plan.data_limit_gb, float(plan.price)) for plan in seller_plans} == {
        ("10GB 1 Month", 30, 10, 10000.0),
        ("10GB 3 Months", 90, 10, 25000.0),
        ("10GB 3 Months Discount", 90, 10, 20000.0),
        ("20GB 1 Month", 30, 20, 20000.0),
        ("20GB 3 Months", 90, 20, 50000.0),
        ("20GB 3 Months Discount", 90, 20, 40000.0),
    }


@pytest.mark.asyncio
async def test_rejected_payment_is_visible_in_buyer_order_status() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    master_service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await master_service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="seller_a_bot",
            bot_token="123:secret",
            volume_limit_gb=500,
        )
        seller_context = SellerContextService(seller_bot.id)
        await seller_context.register_buyer(telegram_id=222, username="buyer")
        plan = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="reseller30",
            price=100000,
            duration_days=30,
            data_limit_gb=30,
        )
        payment_request = await seller_context.request_card_to_card_payment(
            buyer_telegram_id=222,
            plan_id=plan.id,
        )

        rejected = await seller_context.reject_payment(
            admin_telegram_id=111,
            payment_id=payment_request.payment.id,
            reason="رسید خوانا نیست",
        )
        pending = await seller_context.list_pending_payments(admin_telegram_id=111)
        status = await seller_context.get_buyer_order_status(
            buyer_telegram_id=222,
            order_id=payment_request.order.id,
        )
        orders = await seller_context.list_buyer_order_statuses(buyer_telegram_id=222)

        await master_service.register_reseller(telegram_id=333, display_name="Seller B")
        other_seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=333,
            bot_name="seller_b_bot",
            bot_token="456:secret",
            volume_limit_gb=500,
        )
        other_context = SellerContextService(other_seller_bot.id)
        await other_context.register_buyer(telegram_id=222, username="buyer")
        other_plan = await master_service.create_reseller_plan(
            reseller_telegram_id=333,
            name="other30",
            price=120000,
            duration_days=30,
            data_limit_gb=40,
        )
        other_request = await other_context.request_card_to_card_payment(
            buyer_telegram_id=222,
            plan_id=other_plan.id,
        )
        scoped_orders = await seller_context.list_buyer_order_statuses(buyer_telegram_id=222)
    finally:
        await dispose_engine()

    assert rejected.payment.status == "rejected"
    assert rejected.payment.rejection_reason == "رسید خوانا نیست"
    assert rejected.order.status == "canceled"
    assert rejected.buyer.telegram_user_id == 222
    assert pending == []
    assert status.payment is not None
    assert status.payment.status == "rejected"
    assert status.payment.rejection_reason == "رسید خوانا نیست"
    assert [item.order.id for item in orders] == [payment_request.order.id]
    assert other_request.order.id not in {item.order.id for item in scoped_orders}


@pytest.mark.asyncio
async def test_seller_bot_volume_limit_blocks_payments_and_reserves_pending_orders() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    master_service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await master_service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="seller_a_bot",
            bot_token="123:secret",
            volume_limit_gb=50,
        )
        seller_context = SellerContextService(seller_bot.id)
        await seller_context.register_buyer(telegram_id=222, username="buyer")
        plan_30 = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="30gb",
            price=100000,
            duration_days=30,
            data_limit_gb=30,
        )
        plan_25 = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="25gb",
            price=90000,
            duration_days=30,
            data_limit_gb=25,
        )
        unlimited_plan = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="unlimited",
            price=200000,
            duration_days=30,
            data_limit_gb=None,
        )

        first_request = await seller_context.request_card_to_card_payment(
            buyer_telegram_id=222,
            plan_id=plan_30.id,
        )
        quota_after_first = await master_service.seller_bot_quota(seller_bot_id=seller_bot.id)
        with pytest.raises(ValueError, match="seller_bot_volume_limit_exceeded"):
            await seller_context.request_card_to_card_payment(
                buyer_telegram_id=222,
                plan_id=plan_25.id,
            )
        with pytest.raises(ValueError, match="seller_bot_volume_limit_exceeded"):
            await seller_context.request_card_to_card_payment(
                buyer_telegram_id=222,
                plan_id=unlimited_plan.id,
            )
    finally:
        await dispose_engine()

    assert first_request.order.seller_bot_id == seller_bot.id
    assert first_request.payment.seller_bot_id == seller_bot.id
    assert quota_after_first.limit_gb == 50
    assert quota_after_first.used_gb == 0
    assert quota_after_first.reserved_gb == 30
    assert quota_after_first.remaining_gb == 20


@pytest.mark.asyncio
async def test_simple_seller_profile_uses_platform_tables() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    master_service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await master_service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="simple_seller_bot",
            bot_token="123:secret",
            volume_limit_gb=500,
            ui_profile=SellerBotUiProfile.SIMPLE_SELLER,
        )
        seller_context = SellerContextService(seller_bot.id)
        profile = await seller_context.register_buyer(telegram_id=222, username="buyer")
        plan = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="simple30",
            price=100000,
            duration_days=30,
            data_limit_gb=30,
        )
        payment_request = await seller_context.request_card_to_card_payment(
            buyer_telegram_id=222,
            plan_id=plan.id,
        )

        async with session_scope() as session:
            stored_buyer = await session.get(Buyer, profile.buyer.id)
            stored_order = await session.get(Order, payment_request.order.id)
            stored_payment = await session.get(Payment, payment_request.payment.id)
    finally:
        await dispose_engine()

    assert seller_bot.ui_profile == SellerBotUiProfile.SIMPLE_SELLER.value
    assert seller_bot.external_template_id is None
    assert stored_buyer is not None
    assert stored_buyer.reseller_id == seller_bot.reseller_id
    assert stored_order is not None
    assert stored_order.seller_bot_id == seller_bot.id
    assert stored_order.reseller_id == seller_bot.reseller_id
    assert stored_payment is not None
    assert stored_payment.seller_bot_id == seller_bot.id
    assert stored_payment.reseller_id == seller_bot.reseller_id


@pytest.mark.asyncio
async def test_seller_bot_default_zero_blocks_until_master_adds_gb() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    master_service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await master_service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="seller_a_bot",
            bot_token="123:secret",
        )
        seller_context = SellerContextService(seller_bot.id)
        await seller_context.register_buyer(telegram_id=222, username="buyer")
        plan = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="10gb",
            price=100000,
            duration_days=30,
            data_limit_gb=10,
        )

        quota_before = await master_service.seller_bot_quota(seller_bot_id=seller_bot.id)
        seller_admin_quota_before = await seller_context.get_seller_bot_quota(admin_telegram_id=111)
        with pytest.raises(ValueError, match="seller_bot_volume_limit_exceeded"):
            await seller_context.request_card_to_card_payment(
                buyer_telegram_id=222,
                plan_id=plan.id,
            )
        quota_after_add = await master_service.add_seller_bot_volume(
            seller_bot_id=seller_bot.id,
            added_gb=25,
            actor_telegram_id=999,
        )
        payment_request = await seller_context.request_card_to_card_payment(
            buyer_telegram_id=222,
            plan_id=plan.id,
        )
        quota_after_order = await master_service.seller_bot_quota(seller_bot_id=seller_bot.id)
        audit_logs = await master_service.recent_audit_logs(limit=5)
    finally:
        await dispose_engine()

    assert seller_bot.volume_limit_gb == 0
    assert quota_before.limit_gb == 0
    assert quota_before.remaining_gb == 0
    assert seller_admin_quota_before.limit_gb == 0
    assert seller_admin_quota_before.remaining_gb == 0
    assert quota_after_add.limit_gb == 25
    assert quota_after_add.remaining_gb == 25
    assert payment_request.order.seller_bot_id == seller_bot.id
    assert quota_after_order.reserved_gb == 10
    assert quota_after_order.remaining_gb == 15
    assert any(log.action == "seller_bot.volume_add" for log in audit_logs)


@pytest.mark.asyncio
async def test_seller_bot_volume_limit_blocks_wallet_purchase_before_debit() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    master_service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await master_service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="seller_a_bot",
            bot_token="123:secret",
            volume_limit_gb=20,
        )
        seller_context = SellerContextService(seller_bot.id)
        await seller_context.register_buyer(telegram_id=222, username="buyer")
        plan = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="30gb",
            price=100000,
            duration_days=30,
            data_limit_gb=30,
        )
        charge = await seller_context.request_wallet_charge(buyer_telegram_id=222, amount=150000)
        await seller_context.approve_wallet_charge(admin_telegram_id=111, transaction_id=charge.transaction.id)

        with pytest.raises(ValueError, match="seller_bot_volume_limit_exceeded"):
            await seller_context.purchase_with_wallet(buyer_telegram_id=222, plan_id=plan.id)
        buyer_wallet = await seller_context.list_buyer_wallet(buyer_telegram_id=222)
    finally:
        await dispose_engine()

    assert buyer_wallet.buyer is not None
    assert buyer_wallet.buyer.wallet_balance == 150000
    assert all("wallet purchase order" not in (transaction.note or "") for transaction in buyer_wallet.transactions)


@pytest.mark.asyncio
async def test_seller_bot_volume_limit_rechecked_before_provisioning() -> None:
    FakeMarzbanClient.created_users = []
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    fernet_key = Fernet.generate_key().decode("utf-8")
    secret_box = SecretBox(fernet_key)
    master_service = ResellerService(secret_box)

    try:
        await master_service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="seller_a_bot",
            bot_token="123:secret",
            volume_limit_gb=50,
        )
        seller_context = SellerContextService(seller_bot.id)
        await seller_context.register_buyer(telegram_id=222, username="buyer")
        plan = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="40gb",
            price=100000,
            duration_days=30,
            data_limit_gb=40,
        )
        panel = await master_service.register_marzban_panel(
            name="panel-a",
            base_url="https://panel.example.com",
            token="panel-token",
        )
        await master_service.assign_panel(reseller_telegram_id=111, panel_id=panel.id)
        charge = await seller_context.request_wallet_charge(buyer_telegram_id=222, amount=150000)
        await seller_context.approve_wallet_charge(admin_telegram_id=111, transaction_id=charge.transaction.id)
        wallet_purchase = await seller_context.purchase_with_wallet(buyer_telegram_id=222, plan_id=plan.id)
        await master_service.set_seller_bot_volume(seller_bot_id=seller_bot.id, volume_limit_gb=30)
        provisioning = ProvisioningService(
            seller_bot_id=seller_bot.id,
            settings=Settings(
                DATABASE_URL="sqlite+aiosqlite:///:memory:",
                FERNET_KEY=fernet_key,
                MARZBAN_DEFAULT_PROXIES_JSON='{"vless": {}}',
            ),
            secret_box=secret_box,
            marzban_client_factory=FakeMarzbanClient,
        )

        with pytest.raises(ValueError, match="seller_bot_volume_limit_exceeded"):
            await provisioning.provision_buyer_order(
                buyer_telegram_id=222,
                order_id=wallet_purchase.order.id,
            )
    finally:
        await dispose_engine()

    assert FakeMarzbanClient.created_users == []


@pytest.mark.asyncio
async def test_seller_bot_quota_ignores_expired_and_inactive_services() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    master_service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await master_service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="seller_a_bot",
            bot_token="123:secret",
            volume_limit_gb=50,
        )
        seller_context = SellerContextService(seller_bot.id)
        profile = await seller_context.register_buyer(telegram_id=222, username="buyer")
        panel = await master_service.register_marzban_panel(
            name="panel-a",
            base_url="https://panel.example.com",
            token="panel-token",
        )
        async with session_scope() as session:
            await create_vpn_service(
                session,
                reseller_id=seller_bot.reseller_id,
                seller_bot_id=seller_bot.id,
                buyer_id=profile.buyer.id,
                panel_id=panel.id,
                marzban_username="expired_user",
                subscription_url=None,
                data_limit_gb=40,
                expire_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
            )
            inactive = await create_vpn_service(
                session,
                reseller_id=seller_bot.reseller_id,
                seller_bot_id=seller_bot.id,
                buyer_id=profile.buyer.id,
                panel_id=panel.id,
                marzban_username="inactive_user",
                subscription_url=None,
                data_limit_gb=30,
                expire_at=None,
            )
            inactive.is_active = False
            await session.flush()
        quota = await master_service.seller_bot_quota(seller_bot_id=seller_bot.id)
    finally:
        await dispose_engine()

    assert quota.used_gb == 0
    assert quota.remaining_gb == 50


@pytest.mark.asyncio
async def test_register_buyer_is_scoped_to_seller_reseller() -> None:
    FakeMarzbanClient.created_users = []
    FakeMarzbanClient.revoked_users = []
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    fernet_key = Fernet.generate_key().decode("utf-8")
    secret_box = SecretBox(fernet_key)
    master_service = ResellerService(secret_box)

    try:
        registered = await master_service.register_reseller(
            telegram_id=111,
            display_name="Seller A",
        )
        seller_bot = await master_service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="seller_a_bot",
            bot_token="123:secret",
            volume_limit_gb=500,
        )
        seller_context = SellerContextService(seller_bot.id)
        crypto_settings = Settings(
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            FERNET_KEY=fernet_key,
        )
        crypto_context = SellerContextService(seller_bot.id, crypto_settings)
        crypto_config = await crypto_context.set_crypto_payment_config(
            admin_telegram_id=111,
            currency="USDT",
            network="TRC20",
            wallet_address="TExampleWalletAddress123",
            note="Send tx hash after payment.",
        )
        loaded_crypto_config = await crypto_context.get_crypto_payment_config(admin_telegram_id=111)
        support_settings = await seller_context.set_support_telegram_id(
            admin_telegram_id=111,
            support_telegram_id=444,
        )
        loaded_support_settings = await seller_context.get_support_settings(admin_telegram_id=111)
        buyer_support_telegram_id = await seller_context.get_support_telegram_id_for_buyer(buyer_telegram_id=222)
        username_support_settings = await seller_context.set_support_contact(
            admin_telegram_id=111,
            support_contact="@support_user",
        )
        buyer_support_username = await seller_context.get_support_contact_for_buyer(buyer_telegram_id=222)
        deleted_support_settings = await seller_context.delete_support_telegram_id(admin_telegram_id=111)
        profile = await seller_context.register_buyer(
            telegram_id=222,
            username="buyer",
            first_name="Buyer",
        )
        await seller_context.register_buyer(telegram_id=333, username="buyer2")
        wallet_charge = await seller_context.request_wallet_charge(
            buyer_telegram_id=222,
            amount=500000,
        )
        wallet_receipt = await seller_context.attach_wallet_charge_receipt(
            buyer_telegram_id=222,
            transaction_id=wallet_charge.transaction.id,
            file_id="wallet-proof-file-id",
        )
        pending_wallet = await seller_context.list_pending_wallet_charges(admin_telegram_id=111)
        approved_wallet = await seller_context.approve_wallet_charge(
            admin_telegram_id=111,
            transaction_id=wallet_charge.transaction.id,
        )
        buyer_wallet = await seller_context.list_buyer_wallet(buyer_telegram_id=222)
        ticket = await seller_context.open_ticket(
            buyer_telegram_id=222,
            subject="Need help",
            body="My config is slow",
        )
        buyer_ticket_reply = await seller_context.reply_ticket_as_buyer(
            buyer_telegram_id=222,
            ticket_id=ticket.ticket.id,
            body="Adding details",
        )
        admin_ticket_reply = await seller_context.reply_ticket_as_admin(
            admin_telegram_id=111,
            ticket_id=ticket.ticket.id,
            body="We are checking",
        )
        buyer_tickets = await seller_context.list_my_tickets(buyer_telegram_id=222)
        open_tickets = await seller_context.list_open_tickets(admin_telegram_id=111)
        closed_ticket = await seller_context.close_ticket(
            admin_telegram_id=111,
            ticket_id=ticket.ticket.id,
        )
        broadcast = await seller_context.create_broadcast(
            admin_telegram_id=111,
            title="Update",
            body="New plans are available",
        )
        broadcast_recipients = await seller_context.get_broadcast_recipients(
            admin_telegram_id=111,
            broadcast_id=broadcast.broadcast.id,
        )
        sent_broadcast = await seller_context.mark_broadcast_sent(
            admin_telegram_id=111,
            broadcast_id=broadcast.broadcast.id,
            delivered_telegram_ids={222, 333},
        )
        global_broadcast = await master_service.create_global_broadcast(
            admin_telegram_id=111,
            title="Global update",
            body="Hello all buyers",
        )
        global_recipients = await master_service.get_global_broadcast_recipients(
            broadcast_id=global_broadcast.broadcast.id,
        )
        sent_global = await master_service.mark_global_broadcast_sent(
            broadcast_id=global_broadcast.broadcast.id,
            delivered_telegram_ids={222, 333},
        )
        global_plan = await master_service.create_global_plan(
            name="global30",
            price=100000,
            duration_days=30,
            data_limit_gb=30,
        )
        extra_volume_plan = await master_service.create_global_plan(
            name="extra10",
            price=30000,
            duration_days=0,
            data_limit_gb=10,
            purpose=PlanPurpose.EXTRA_VOLUME,
        )
        reseller_plan = await master_service.create_reseller_plan(
            reseller_telegram_id=111,
            name="reseller60",
            price=180000,
            duration_days=60,
            data_limit_gb=60,
        )
        seller_admin_plan = await seller_context.create_admin_plan(
            admin_telegram_id=111,
            name="seller-admin45",
            price=99000,
            duration_days=45,
            data_limit_gb=70,
        )
        seller_admin_plan = await seller_context.update_admin_plan(
            admin_telegram_id=111,
            plan_id=seller_admin_plan.id,
            name="seller-admin90",
            price=149000,
            duration_days=90,
            data_limit_gb=120,
        )
        removable_admin_plan = await seller_context.create_admin_plan(
            admin_telegram_id=111,
            name="removable-plan",
            price=59000,
            duration_days=15,
            data_limit_gb=20,
        )
        deleted_admin_plan = await seller_context.deactivate_admin_plan(
            admin_telegram_id=111,
            plan_id=removable_admin_plan.id,
        )
        admin_plans = await seller_context.list_admin_plans(admin_telegram_id=111)
        discount = await master_service.create_global_discount(
            code="SAVE10",
            discount_type=DiscountType.PERCENT,
            amount=10,
            max_uses=5,
        )
        panel = await master_service.register_marzban_panel(
            name="panel-a",
            base_url="https://panel.example.com",
            token="panel-token",
        )
        await master_service.assign_panel(
            reseller_telegram_id=111,
            panel_id=panel.id,
            marzban_admin_username="reseller_owner",
        )
        plans = await seller_context.list_plans()
        payment_request = await seller_context.request_card_to_card_payment(
            buyer_telegram_id=222,
            plan_id=reseller_plan.id,
            coupon_code="save10",
        )
        payment_receipt = await seller_context.attach_payment_receipt(
            buyer_telegram_id=222,
            payment_id=payment_request.payment.id,
            file_id="payment-proof-file-id",
        )
        discounts_after_purchase = await master_service.list_discounts()
        pending = await seller_context.list_pending_payments(admin_telegram_id=111)
        approved = await seller_context.approve_payment(
            admin_telegram_id=111,
            payment_id=payment_request.payment.id,
        )
        settings = Settings(
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            FERNET_KEY=fernet_key,
            MARZBAN_DEFAULT_PROXIES_JSON='{"vless": {}}',
        )
        provisioning = ProvisioningService(
            seller_bot_id=seller_bot.id,
            settings=settings,
            secret_box=secret_box,
            marzban_client_factory=FakeMarzbanClient,
        )
        wallet_purchase = await seller_context.purchase_with_wallet(
            buyer_telegram_id=222,
            plan_id=reseller_plan.id,
            coupon_code="save10",
            requested_username="sina_home",
        )
        discounts_after_purchase = await master_service.list_discounts()
        provisioned = await provisioning.provision_buyer_order(
            buyer_telegram_id=222,
            order_id=wallet_purchase.order.id,
        )
        reprovisioned = await provisioning.provision_buyer_order(
            buyer_telegram_id=222,
            order_id=wallet_purchase.order.id,
        )
        buyer_services = await seller_context.list_buyer_services(buyer_telegram_id=222)
        revoked_service = await provisioning.revoke_subscription_link(
            buyer_telegram_id=222,
            service_id=provisioned.vpn_service.id,
        )
        with pytest.raises(ValueError, match="service_not_found"):
            await provisioning.revoke_subscription_link(
                buyer_telegram_id=333,
                service_id=provisioned.vpn_service.id,
            )
        customer_search_by_id = await seller_context.search_customers(admin_telegram_id=111, query="222")
        customer_search_by_username = await seller_context.search_customers(admin_telegram_id=111, query="@buyer")
        customer_search_by_service = await seller_context.search_customers(
            admin_telegram_id=111,
            query=provisioned.vpn_service.marzban_username,
        )
        customer_detail = await seller_context.get_customer_detail(
            admin_telegram_id=111,
            buyer_id=profile.buyer.id,
        )
        renewal_request = await seller_context.request_renewal_payment(
            buyer_telegram_id=222,
            service_id=provisioned.vpn_service.id,
            plan_id=global_plan.id,
        )
        renewal_approved = await seller_context.approve_payment(
            admin_telegram_id=111,
            payment_id=renewal_request.payment.id,
        )
        renewed = await provisioning.apply_renewal(
            admin_telegram_id=111,
            order_id=renewal_approved.order.id,
        )
        extra_volume_request = await seller_context.request_extra_volume_payment(
            buyer_telegram_id=222,
            service_id=provisioned.vpn_service.id,
            plan_id=extra_volume_plan.id,
        )
        extra_volume_approved = await seller_context.approve_payment(
            admin_telegram_id=111,
            payment_id=extra_volume_request.payment.id,
        )
        volume_applied = await provisioning.apply_extra_volume(
            admin_telegram_id=111,
            order_id=extra_volume_approved.order.id,
        )
        reseller_report = await seller_context.sales_report(admin_telegram_id=111, days=7)
        global_report = await master_service.global_report(days=7)
        trial_service = await provisioning.provision_trial(buyer_telegram_id=333)
        with pytest.raises(ValueError, match="trial_already_used"):
            await provisioning.provision_trial(buyer_telegram_id=333)
    finally:
        await dispose_engine()

    assert profile.reseller.id == registered.reseller.id
    assert crypto_config.currency == "USDT"
    assert loaded_crypto_config is not None
    assert loaded_crypto_config.network == "TRC20"
    assert loaded_crypto_config.wallet_address == "TExampleWalletAddress123"
    assert support_settings.telegram_id == 444
    assert loaded_support_settings.telegram_id == 444
    assert buyer_support_telegram_id == 444
    assert username_support_settings.contact == "@support_user"
    assert buyer_support_username == "@support_user"
    assert deleted_support_settings.telegram_id is None
    assert profile.seller_bot.id == seller_bot.id
    assert profile.buyer.reseller_id == registered.reseller.id
    assert profile.buyer.telegram_user_id == 222
    assert deleted_admin_plan.is_active is False
    assert removable_admin_plan.id not in {plan.id for plan in admin_plans}
    assert wallet_receipt.proof_file_id == "wallet-proof-file-id"
    assert pending_wallet[0].id == wallet_charge.transaction.id
    assert pending_wallet[0].proof_file_id == "wallet-proof-file-id"
    assert approved_wallet.transaction.status == "completed"
    assert approved_wallet.transaction.transaction_type == "charge_approved"
    assert buyer_wallet.buyer is not None
    assert buyer_wallet.buyer.wallet_balance == 500000
    assert ticket.ticket.subject == "Need help"
    assert len(buyer_ticket_reply.messages) == 2
    assert len(admin_ticket_reply.messages) == 3
    assert [item.id for item in buyer_tickets] == [ticket.ticket.id]
    assert [item.id for item in open_tickets] == [ticket.ticket.id]
    assert closed_ticket.status == "closed"
    assert len(broadcast.recipients) == 2
    assert len(broadcast_recipients.recipients) == 2
    assert sent_broadcast.sent_count == 2
    assert sent_broadcast.status == "sent"
    assert len(global_broadcast.recipients) == 2
    assert len(global_recipients.recipients) == 2
    assert sent_global.sent_count == 2
    assert sent_global.status == "sent"
    assert {plan.id for plan in plans} == {global_plan.id, reseller_plan.id, seller_admin_plan.id}
    assert payment_request.payment.amount == 162000
    assert payment_receipt.proof_file_id == "payment-proof-file-id"
    assert discount.id in {item.id for item in discounts_after_purchase}
    assert [item.used_count for item in discounts_after_purchase if item.id == discount.id] == [2]
    assert payment_request.plan.id == reseller_plan.id
    assert payment_request.order.buyer_id == profile.buyer.id
    assert payment_request.order.status == "waiting_payment"
    assert payment_request.payment.order_id == payment_request.order.id
    assert payment_request.payment.status == "pending"
    assert payment_request.payment.method == "card_to_card"
    assert len(pending) == 1
    assert pending[0].payment.id == payment_request.payment.id
    assert pending[0].payment.proof_file_id == "payment-proof-file-id"
    assert approved.payment.status == "approved"
    assert approved.payment.approved_by_telegram_id == 111
    assert approved.order.status == "provisioning"
    assert approved.buyer.telegram_user_id == 222
    assert provisioned.order.status == "completed"
    assert provisioned.order.target_service_id == provisioned.vpn_service.id
    assert reprovisioned.vpn_service.id == provisioned.vpn_service.id
    assert provisioned.vpn_service.buyer_id == profile.buyer.id
    assert provisioned.vpn_service.panel_id == panel.id
    assert provisioned.vpn_service.subscription_url is not None
    assert FakeMarzbanClient.revoked_users == [provisioned.vpn_service.marzban_username]
    assert revoked_service.subscription_url is not None
    assert revoked_service.subscription_url.endswith(f"/revoked/{provisioned.vpn_service.marzban_username}")
    assert FakeMarzbanClient.created_users[0].proxies == {"vless": {}, "vmess": {}, "trojan": {}}
    assert FakeMarzbanClient.created_users[0].inbounds == {
        "vless": ["VLESS TCP REALITY"],
        "vmess": ["VMess WS TLS"],
        "trojan": ["Trojan TCP TLS"],
    }
    assert [service.id for service in buyer_services] == [provisioned.vpn_service.id]
    assert [item.buyer.id for item in customer_search_by_id] == [profile.buyer.id]
    assert [item.buyer.id for item in customer_search_by_username] == [profile.buyer.id]
    assert [item.buyer.id for item in customer_search_by_service] == [profile.buyer.id]
    assert customer_detail.buyer.id == profile.buyer.id
    assert customer_detail.service_count == 1
    assert customer_detail.order_count == 2
    assert customer_detail.ticket_count == 1
    assert renewal_request.order.order_type == "renewal"
    assert renewal_request.order.target_service_id == provisioned.vpn_service.id
    assert renewed.order.status == "completed"
    assert renewed.vpn_service.id == provisioned.vpn_service.id
    assert renewed.vpn_service.data_limit_gb == reseller_plan.data_limit_gb + global_plan.data_limit_gb
    assert extra_volume_request.order.order_type == "extra_volume"
    assert extra_volume_request.order.target_service_id == provisioned.vpn_service.id
    assert volume_applied.order.status == "completed"
    assert volume_applied.vpn_service.id == provisioned.vpn_service.id
    assert volume_applied.vpn_service.data_limit_gb == (
        reseller_plan.data_limit_gb + global_plan.data_limit_gb + extra_volume_plan.data_limit_gb
    )
    assert reseller_report["completed_orders"] >= 3
    assert reseller_report["new_services"] >= 1
    assert global_report["completed_orders"] >= 3
    assert global_report["resellers"] == 1
    assert trial_service.data_limit_gb == 1
    assert trial_service.subscription_url is not None
