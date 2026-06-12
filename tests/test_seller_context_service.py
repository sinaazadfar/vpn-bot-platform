from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from vpn_bot_platform.common.config import Settings
from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine
from vpn_bot_platform.common.models import DiscountType, PlanPurpose
from vpn_bot_platform.integrations.marzban import (
    MarzbanCredentials,
    MarzbanUserCreate,
    MarzbanUserUpdate,
)
from vpn_bot_platform.master_bot.services.resellers import ResellerService
from vpn_bot_platform.seller_bot.provisioning import ProvisioningService
from vpn_bot_platform.seller_bot.services import SellerContextService


class FakeMarzbanClient:
    def __init__(self, credentials: MarzbanCredentials) -> None:
        self.credentials = credentials

    async def create_user(self, user: MarzbanUserCreate) -> dict:
        return {
            "username": user.username,
            "subscription_url": f"{self.credentials.base_url}/sub/{user.username}",
        }

    async def update_user(self, username: str, update: MarzbanUserUpdate) -> dict:
        return {"username": username, **update.to_payload()}


@pytest.mark.asyncio
async def test_register_buyer_is_scoped_to_seller_reseller() -> None:
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
        profile = await seller_context.register_buyer(
            telegram_id=222,
            username="buyer",
            first_name="Buyer",
        )
        await seller_context.register_buyer(telegram_id=333, username="buyer2")
        wallet_charge = await seller_context.request_wallet_charge(
            buyer_telegram_id=222,
            amount=50000,
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
        renewal_plan = await master_service.create_global_plan(
            name="renew30",
            price=90000,
            duration_days=30,
            data_limit_gb=30,
            purpose=PlanPurpose.RENEWAL,
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
            data_limit_gb=None,
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
        provisioned = await provisioning.provision_order(
            admin_telegram_id=111,
            order_id=approved.order.id,
        )
        buyer_services = await seller_context.list_buyer_services(buyer_telegram_id=222)
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
            plan_id=renewal_plan.id,
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
    assert profile.seller_bot.id == seller_bot.id
    assert profile.buyer.reseller_id == registered.reseller.id
    assert profile.buyer.telegram_user_id == 222
    assert pending_wallet[0].id == wallet_charge.transaction.id
    assert approved_wallet.transaction.status == "completed"
    assert approved_wallet.transaction.transaction_type == "charge_approved"
    assert buyer_wallet.buyer is not None
    assert buyer_wallet.buyer.wallet_balance == 50000
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
    assert seller_admin_plan.reseller_id == registered.reseller.id
    assert seller_admin_plan.name == "seller-admin90"
    assert seller_admin_plan.price == 149000
    assert seller_admin_plan.duration_days == 90
    assert seller_admin_plan.data_limit_gb == 120
    assert deleted_admin_plan.id == removable_admin_plan.id
    assert deleted_admin_plan.is_active is False
    assert removable_admin_plan.id not in {plan.id for plan in plans}
    assert seller_admin_plan.id in {plan.id for plan in admin_plans}
    assert payment_request.payment.amount == 162000
    assert discount.id in {item.id for item in discounts_after_purchase}
    assert [item.used_count for item in discounts_after_purchase if item.id == discount.id] == [1]
    assert payment_request.plan.id == reseller_plan.id
    assert payment_request.order.buyer_id == profile.buyer.id
    assert payment_request.order.status == "waiting_payment"
    assert payment_request.payment.order_id == payment_request.order.id
    assert payment_request.payment.status == "pending"
    assert payment_request.payment.method == "card_to_card"
    assert len(pending) == 1
    assert pending[0].payment.id == payment_request.payment.id
    assert approved.payment.status == "approved"
    assert approved.payment.approved_by_telegram_id == 111
    assert approved.order.status == "provisioning"
    assert provisioned.order.status == "completed"
    assert provisioned.vpn_service.buyer_id == profile.buyer.id
    assert provisioned.vpn_service.panel_id == panel.id
    assert provisioned.vpn_service.subscription_url is not None
    assert [service.id for service in buyer_services] == [provisioned.vpn_service.id]
    assert [item.buyer.id for item in customer_search_by_id] == [profile.buyer.id]
    assert [item.buyer.id for item in customer_search_by_username] == [profile.buyer.id]
    assert [item.buyer.id for item in customer_search_by_service] == [profile.buyer.id]
    assert customer_detail.buyer.id == profile.buyer.id
    assert customer_detail.service_count == 1
    assert customer_detail.order_count == 1
    assert customer_detail.ticket_count == 1
    assert renewal_request.order.order_type == "renewal"
    assert renewal_request.order.target_service_id == provisioned.vpn_service.id
    assert renewed.order.status == "completed"
    assert renewed.vpn_service.id == provisioned.vpn_service.id
    assert renewed.vpn_service.data_limit_gb == renewal_plan.data_limit_gb
    assert extra_volume_request.order.order_type == "extra_volume"
    assert extra_volume_request.order.target_service_id == provisioned.vpn_service.id
    assert volume_applied.order.status == "completed"
    assert volume_applied.vpn_service.id == provisioned.vpn_service.id
    assert volume_applied.vpn_service.data_limit_gb == renewal_plan.data_limit_gb + extra_volume_plan.data_limit_gb
    assert reseller_report["completed_orders"] >= 3
    assert reseller_report["new_services"] >= 1
    assert global_report["completed_orders"] >= 3
    assert global_report["resellers"] == 1
    assert trial_service.data_limit_gb == 1
    assert trial_service.subscription_url is not None
