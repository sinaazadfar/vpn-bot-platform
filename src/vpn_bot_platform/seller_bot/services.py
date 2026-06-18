from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json

from vpn_bot_platform.common.config import Settings
from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import session_scope
from vpn_bot_platform.common.models import (
    AuditActorType,
    Buyer,
    Broadcast,
    BroadcastRecipient,
    Order,
    OrderType,
    Payment,
    PaymentGateway,
    PaymentGatewayStatus,
    Plan,
    PlanPurpose,
    Reseller,
    SellerBot,
    TelegramUser,
    VpnService,
    WalletTransaction,
    Ticket,
    TicketMessage,
    TicketMessageSenderType,
    PaymentStatus,
    WalletOwnerType,
    WalletTransactionStatus,
    WalletTransactionType,
)
from vpn_bot_platform.common.repositories import (
    approve_payment,
    approve_buyer_wallet_charge,
    add_ticket_message,
    close_ticket,
    apply_discount_amount,
    create_order_with_pending_payment,
    create_buyer_wallet_charge_request,
    create_wallet_purchase_order,
    create_plan,
    create_ticket,
    delete_reseller_setting,
    create_reseller_broadcast,
    get_active_plan_for_reseller,
    get_active_discount_code,
    get_buyer_order_status,
    get_customer_counts,
    get_customer_for_reseller,
    get_active_payment_gateway,
    get_plan,
    get_reseller_setting,
    get_seller_bot_with_reseller,
    get_ticket_for_buyer,
    get_ticket_for_reseller,
    get_broadcast_for_reseller,
    get_vpn_service_for_buyer,
    list_pending_payments_for_reseller,
    list_provisioning_orders_for_reseller,
    list_buyer_order_statuses,
    list_pending_wallet_charges_for_reseller,
    list_customers_for_reseller,
    list_buyer_tickets,
    list_open_tickets_for_reseller,
    list_ticket_messages,
    list_pending_broadcast_recipients,
    mark_broadcast_sent,
    reseller_sales_report,
    record_audit_log,
    set_plan_active,
    list_wallet_transactions_for_buyer,
    increment_discount_usage,
    reject_payment,
    list_vpn_services_for_buyer,
    list_active_plans_for_reseller,
    search_customers_for_reseller,
    set_reseller_setting,
    upsert_payment_gateway,
    upsert_buyer,
)
from vpn_bot_platform.integrations.payments import (
    PaymentGatewayRegistry,
    default_payment_registry,
)

SUPPORT_TELEGRAM_ID_SETTING = "support_telegram_id"


@dataclass(frozen=True)
class BuyerProfile:
    buyer: Buyer
    reseller: Reseller
    seller_bot: SellerBot


@dataclass(frozen=True)
class PaymentRequest:
    order: Order
    payment: Payment
    plan: Plan
    instructions: str


@dataclass(frozen=True)
class PaymentQuote:
    plan: Plan
    amount: float
    coupon_code: str | None = None


@dataclass(frozen=True)
class WalletPurchase:
    order: Order
    transaction: WalletTransaction
    plan: Plan
    buyer: Buyer


@dataclass(frozen=True)
class BuyerOrderStatus:
    order: Order
    payment: Payment | None
    plan: Plan | None


@dataclass(frozen=True)
class PaymentNotificationContacts:
    admin_telegram_id: int
    support_contact: int | str | None = None


@dataclass(frozen=True)
class PendingPayment:
    payment: Payment
    order: Order
    plan: Plan


@dataclass(frozen=True)
class ProvisioningOrder:
    order: Order
    buyer: Buyer
    plan: Plan


@dataclass(frozen=True)
class SellerCustomer:
    buyer: Buyer
    telegram_user: TelegramUser


@dataclass(frozen=True)
class SellerCustomerDetail:
    buyer: Buyer
    telegram_user: TelegramUser
    service_count: int
    order_count: int
    ticket_count: int


@dataclass(frozen=True)
class ApprovedPayment:
    payment: Payment
    order: Order
    buyer: Buyer


@dataclass(frozen=True)
class RejectedPayment:
    payment: Payment
    order: Order
    buyer: Buyer


@dataclass(frozen=True)
class WalletChargeRequest:
    transaction: WalletTransaction
    instructions: str


@dataclass(frozen=True)
class CryptoPaymentConfig:
    currency: str
    network: str
    wallet_address: str
    note: str | None = None


@dataclass(frozen=True)
class BuyerWallet:
    buyer: Buyer | None
    transactions: list[WalletTransaction]


@dataclass(frozen=True)
class TicketThread:
    ticket: Ticket
    messages: list[TicketMessage]


@dataclass(frozen=True)
class BroadcastDraft:
    broadcast: Broadcast
    recipients: list[BroadcastRecipient]


@dataclass(frozen=True)
class SupportSettings:
    contact: int | str | None

    @property
    def telegram_id(self) -> int | None:
        return self.contact if isinstance(self.contact, int) else None


class SellerContextService:
    def __init__(
        self,
        seller_bot_id: str,
        settings: Settings | None = None,
        payment_gateways: PaymentGatewayRegistry | None = None,
    ) -> None:
        self.seller_bot_id = seller_bot_id
        self.settings = settings
        self.secret_box = SecretBox(settings.fernet_key) if settings is not None else None
        instructions = (
            settings.card_to_card_instructions
            if settings is not None
            else "Send the card-to-card receipt to support for approval."
        )
        self.payment_gateways = payment_gateways or default_payment_registry(
            card_to_card_instructions=instructions,
        )

    async def register_buyer(
        self,
        *,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> BuyerProfile:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            reseller = seller_bot.reseller
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
            )
            await session.flush()
            return BuyerProfile(buyer=buyer, reseller=reseller, seller_bot=seller_bot)

    async def list_plans(self, *, purpose: PlanPurpose | None = PlanPurpose.PURCHASE) -> list[Plan]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            return await list_active_plans_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                purpose=purpose,
            )

    async def request_card_to_card_payment(
        self,
        *,
        buyer_telegram_id: int,
        plan_id: str,
        coupon_code: str | None = None,
        requested_username: str | None = None,
    ) -> PaymentRequest:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )
            plan = await get_active_plan_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                plan_id=plan_id,
                purpose=PlanPurpose.PURCHASE,
            )
            if plan is None:
                raise ValueError("plan_not_found")
            discount = None
            if coupon_code:
                discount = await get_active_discount_code(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    code=coupon_code,
                )
                if discount is None:
                    raise ValueError("discount_not_found")
            amount = apply_discount_amount(price=float(plan.price), discount=discount)
            order, payment = await create_order_with_pending_payment(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
                plan_id=plan.id,
                amount=amount,
                requested_username=requested_username,
            )
            increment_discount_usage(discount)
            await session.flush()
            crypto_config = self._decrypt_crypto_gateway(
                await get_active_payment_gateway(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    provider="crypto",
                )
            )
            if crypto_config is None:
                intent = self.payment_gateways.get("card_to_card").create_payment_intent(
                    amount=amount,
                    description=f"order:{order.id}",
                    buyer_telegram_id=buyer_telegram_id,
                )
                instructions = intent.instructions
            else:
                payment.method = "crypto"
                instructions = self._crypto_payment_instructions(
                    config=crypto_config,
                    amount=amount,
                    reference=f"order:{order.id}",
                )
            return PaymentRequest(
                order=order,
                payment=payment,
                plan=plan,
                instructions=instructions,
            )

    async def purchase_with_wallet(
        self,
        *,
        buyer_telegram_id: int,
        plan_id: str,
        coupon_code: str | None = None,
        requested_username: str | None = None,
    ) -> WalletPurchase:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )
            plan = await get_active_plan_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                plan_id=plan_id,
                purpose=PlanPurpose.PURCHASE,
            )
            if plan is None:
                raise ValueError("plan_not_found")
            discount = None
            if coupon_code:
                discount = await get_active_discount_code(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    code=coupon_code,
                )
                if discount is None:
                    raise ValueError("discount_not_found")
            amount = apply_discount_amount(price=float(plan.price), discount=discount)
            result = await create_wallet_purchase_order(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
                plan_id=plan.id,
                amount=amount,
                requested_username=requested_username,
            )
            if result is None:
                raise ValueError("insufficient_wallet_balance")
            order, transaction, buyer = result
            increment_discount_usage(discount)
            await session.flush()
            return WalletPurchase(order=order, transaction=transaction, plan=plan, buyer=buyer)

    async def quote_card_to_card_payment(
        self,
        *,
        plan_id: str,
        coupon_code: str | None = None,
    ) -> PaymentQuote:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            plan = await get_active_plan_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                plan_id=plan_id,
                purpose=PlanPurpose.PURCHASE,
            )
            if plan is None:
                raise ValueError("plan_not_found")
            discount = None
            normalized_coupon = (coupon_code or "").strip() or None
            if normalized_coupon:
                discount = await get_active_discount_code(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    code=normalized_coupon,
                )
                if discount is None:
                    raise ValueError("discount_not_found")
            amount = apply_discount_amount(price=float(plan.price), discount=discount)
            return PaymentQuote(plan=plan, amount=amount, coupon_code=normalized_coupon)

    async def get_buyer_order_status(
        self,
        *,
        buyer_telegram_id: int,
        order_id: str,
    ) -> BuyerOrderStatus:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            row = await get_buyer_order_status(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
                order_id=order_id,
            )
            if row is None:
                raise ValueError("order_not_found")
            order, payment, plan = row
            return BuyerOrderStatus(order=order, payment=payment, plan=plan)

    async def list_buyer_order_statuses(
        self,
        *,
        buyer_telegram_id: int,
        limit: int = 10,
    ) -> list[BuyerOrderStatus]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            rows = await list_buyer_order_statuses(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
                limit=limit,
            )
            return [
                BuyerOrderStatus(order=order, payment=payment, plan=plan)
                for order, payment, plan in rows
            ]

    async def get_payment_notification_contacts(
        self,
        *,
        buyer_telegram_id: int,
    ) -> PaymentNotificationContacts:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            setting = await get_reseller_setting(
                session,
                reseller_id=seller_bot.reseller_id,
                key=SUPPORT_TELEGRAM_ID_SETTING,
            )
            return PaymentNotificationContacts(
                admin_telegram_id=seller_bot.reseller.telegram_user_id,
                support_contact=self._parse_support_contact(setting.value if setting else None),
            )

    async def request_renewal_payment(
        self,
        *,
        buyer_telegram_id: int,
        service_id: str,
        plan_id: str,
        coupon_code: str | None = None,
    ) -> PaymentRequest:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            service = await get_vpn_service_for_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
                service_id=service_id,
            )
            if service is None:
                raise ValueError("service_not_found")
            plan = await get_active_plan_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                plan_id=plan_id,
                purpose=PlanPurpose.PURCHASE,
            )
            if plan is None:
                raise ValueError("plan_not_found")
            discount = None
            if coupon_code:
                discount = await get_active_discount_code(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    code=coupon_code,
                )
                if discount is None:
                    raise ValueError("discount_not_found")
            amount = apply_discount_amount(price=float(plan.price), discount=discount)
            order, payment = await create_order_with_pending_payment(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=service.buyer_id,
                plan_id=plan.id,
                amount=amount,
                order_type=OrderType.RENEWAL,
                target_service_id=service.id,
            )
            increment_discount_usage(discount)
            await session.flush()
            crypto_config = self._decrypt_crypto_gateway(
                await get_active_payment_gateway(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    provider="crypto",
                )
            )
            if crypto_config is None:
                intent = self.payment_gateways.get("card_to_card").create_payment_intent(
                    amount=amount,
                    description=f"renewal:{order.id}",
                    buyer_telegram_id=buyer_telegram_id,
                )
                instructions = intent.instructions
            else:
                payment.method = "crypto"
                instructions = self._crypto_payment_instructions(
                    config=crypto_config,
                    amount=amount,
                    reference=f"renewal:{order.id}",
                )
            return PaymentRequest(order=order, payment=payment, plan=plan, instructions=instructions)

    async def request_extra_volume_payment(
        self,
        *,
        buyer_telegram_id: int,
        service_id: str,
        plan_id: str,
        coupon_code: str | None = None,
    ) -> PaymentRequest:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            service = await get_vpn_service_for_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
                service_id=service_id,
            )
            if service is None:
                raise ValueError("service_not_found")
            plan = await get_active_plan_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                plan_id=plan_id,
                purpose=PlanPurpose.EXTRA_VOLUME,
            )
            if plan is None:
                raise ValueError("plan_not_found")
            discount = None
            if coupon_code:
                discount = await get_active_discount_code(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    code=coupon_code,
                )
                if discount is None:
                    raise ValueError("discount_not_found")
            amount = apply_discount_amount(price=float(plan.price), discount=discount)
            order, payment = await create_order_with_pending_payment(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=service.buyer_id,
                plan_id=plan.id,
                amount=amount,
                order_type=OrderType.EXTRA_VOLUME,
                target_service_id=service.id,
            )
            increment_discount_usage(discount)
            await session.flush()
            crypto_config = self._decrypt_crypto_gateway(
                await get_active_payment_gateway(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    provider="crypto",
                )
            )
            if crypto_config is None:
                intent = self.payment_gateways.get("card_to_card").create_payment_intent(
                    amount=amount,
                    description=f"extra_volume:{order.id}",
                    buyer_telegram_id=buyer_telegram_id,
                )
                instructions = intent.instructions
            else:
                payment.method = "crypto"
                instructions = self._crypto_payment_instructions(
                    config=crypto_config,
                    amount=amount,
                    reference=f"extra_volume:{order.id}",
                )
            return PaymentRequest(order=order, payment=payment, plan=plan, instructions=instructions)

    async def list_pending_payments(self, *, admin_telegram_id: int) -> list[PendingPayment]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            rows = await list_pending_payments_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
            )
            return [
                PendingPayment(payment=payment, order=order, plan=plan)
                for payment, order, plan in rows
            ]

    async def list_provisioning_orders(self, *, admin_telegram_id: int) -> list[ProvisioningOrder]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            rows = await list_provisioning_orders_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
            )
            return [
                ProvisioningOrder(order=order, buyer=buyer, plan=plan)
                for order, buyer, plan in rows
            ]

    async def list_customers(self, *, admin_telegram_id: int) -> list[SellerCustomer]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            rows = await list_customers_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
            )
            return [
                SellerCustomer(buyer=buyer, telegram_user=telegram_user)
                for buyer, telegram_user in rows
            ]

    async def search_customers(self, *, admin_telegram_id: int, query: str) -> list[SellerCustomer]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            rows = await search_customers_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                query=query,
            )
            return [
                SellerCustomer(buyer=buyer, telegram_user=telegram_user)
                for buyer, telegram_user in rows
            ]

    async def get_customer_detail(self, *, admin_telegram_id: int, buyer_id: str) -> SellerCustomerDetail:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            customer = await get_customer_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer_id,
            )
            if customer is None:
                raise ValueError("customer_not_found")
            buyer, telegram_user = customer
            counts = await get_customer_counts(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
            )
            return SellerCustomerDetail(
                buyer=buyer,
                telegram_user=telegram_user,
                service_count=counts["services"],
                order_count=counts["orders"],
                ticket_count=counts["tickets"],
            )

    async def list_admin_plans(self, *, admin_telegram_id: int) -> list[Plan]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            return await list_active_plans_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
            )

    async def ensure_reseller_admin(self, *, admin_telegram_id: int) -> None:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)

    async def get_support_settings(self, *, admin_telegram_id: int) -> SupportSettings:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            setting = await get_reseller_setting(
                session,
                reseller_id=seller_bot.reseller_id,
                key=SUPPORT_TELEGRAM_ID_SETTING,
            )
            return SupportSettings(contact=self._parse_support_contact(setting.value if setting else None))

    async def get_support_telegram_id_for_buyer(self, *, buyer_telegram_id: int) -> int | str | None:
        return await self.get_support_contact_for_buyer(buyer_telegram_id=buyer_telegram_id)

    async def get_support_contact_for_buyer(self, *, buyer_telegram_id: int) -> int | str | None:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            setting = await get_reseller_setting(
                session,
                reseller_id=seller_bot.reseller_id,
                key=SUPPORT_TELEGRAM_ID_SETTING,
            )
            return self._parse_support_contact(setting.value if setting else None)

    async def set_support_telegram_id(self, *, admin_telegram_id: int, support_telegram_id: int) -> SupportSettings:
        return await self.set_support_contact(
            admin_telegram_id=admin_telegram_id,
            support_contact=str(support_telegram_id),
        )

    async def set_support_contact(self, *, admin_telegram_id: int, support_contact: str) -> SupportSettings:
        normalized_contact = self._normalize_support_contact(support_contact)
        if normalized_contact is None:
            raise ValueError("invalid_support_contact")
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            setting = await set_reseller_setting(
                session,
                reseller_id=seller_bot.reseller_id,
                key=SUPPORT_TELEGRAM_ID_SETTING,
                value=str(normalized_contact),
            )
            await record_audit_log(
                session,
                action="support.contact.set",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="platform_setting",
                target_id=setting.id,
                metadata={"support_contact": str(normalized_contact)},
            )
            await session.flush()
            return SupportSettings(contact=normalized_contact)

    async def delete_support_telegram_id(self, *, admin_telegram_id: int) -> SupportSettings:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            await delete_reseller_setting(
                session,
                reseller_id=seller_bot.reseller_id,
                key=SUPPORT_TELEGRAM_ID_SETTING,
            )
            await record_audit_log(
                session,
                action="support.contact.delete",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="platform_setting",
                target_id=SUPPORT_TELEGRAM_ID_SETTING,
            )
            await session.flush()
            return SupportSettings(contact=None)

    async def get_crypto_payment_config(self, *, admin_telegram_id: int) -> CryptoPaymentConfig | None:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            gateway = await get_active_payment_gateway(
                session,
                reseller_id=seller_bot.reseller_id,
                provider="crypto",
            )
            return self._decrypt_crypto_gateway(gateway)

    async def set_crypto_payment_config(
        self,
        *,
        admin_telegram_id: int,
        currency: str,
        network: str,
        wallet_address: str,
        note: str | None = None,
    ) -> CryptoPaymentConfig:
        if self.secret_box is None:
            raise ValueError("encryption_not_configured")
        config = CryptoPaymentConfig(
            currency=currency.strip(),
            network=network.strip(),
            wallet_address=wallet_address.strip(),
            note=(note or "").strip() or None,
        )
        if not config.currency or not config.network or not config.wallet_address:
            raise ValueError("invalid_crypto_payment_config")
        payload = json.dumps(
            {
                "currency": config.currency,
                "network": config.network,
                "wallet_address": config.wallet_address,
                "note": config.note,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        encrypted_payload = self.secret_box.encrypt(payload)
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            gateway = await upsert_payment_gateway(
                session,
                reseller_id=seller_bot.reseller_id,
                provider="crypto",
                config_encrypted=encrypted_payload,
                priority=10,
                status=PaymentGatewayStatus.ACTIVE,
            )
            await record_audit_log(
                session,
                action="payment_gateway.crypto.upsert",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="payment_gateway",
                target_id=gateway.id,
                metadata={
                    "currency": config.currency,
                    "network": config.network,
                    "has_note": config.note is not None,
                },
            )
            await session.flush()
            return config

    async def create_admin_plan(
        self,
        *,
        admin_telegram_id: int,
        name: str,
        price: float,
        duration_days: int,
        data_limit_gb: int | None,
        purpose: PlanPurpose = PlanPurpose.PURCHASE,
    ) -> Plan:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            plan = await create_plan(
                session,
                reseller_id=seller_bot.reseller_id,
                name=name,
                price=price,
                duration_days=duration_days,
                data_limit_gb=data_limit_gb,
                purpose=purpose,
            )
            await record_audit_log(
                session,
                action="seller_plan.create",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="plan",
                target_id=plan.id,
                metadata={
                    "name": name,
                    "price": price,
                    "duration_days": duration_days,
                    "data_limit_gb": data_limit_gb,
                    "purpose": purpose.value,
                },
            )
            await session.flush()
            return plan

    async def get_admin_plan(
        self,
        *,
        admin_telegram_id: int,
        plan_id: str,
    ) -> Plan:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            plan = await get_plan(session, plan_id=plan_id)
            if plan is None or plan.reseller_id != seller_bot.reseller_id or not plan.is_active:
                raise ValueError("plan_not_found")
            return plan

    async def update_admin_plan(
        self,
        *,
        admin_telegram_id: int,
        plan_id: str,
        name: str,
        price: float,
        duration_days: int,
        data_limit_gb: int,
    ) -> Plan:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            plan = await get_plan(session, plan_id=plan_id)
            if plan is None or plan.reseller_id != seller_bot.reseller_id or not plan.is_active:
                raise ValueError("plan_not_found")
            plan.name = name
            plan.price = price
            plan.duration_days = duration_days
            plan.data_limit_gb = data_limit_gb
            await record_audit_log(
                session,
                action="seller_plan.update",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="plan",
                target_id=plan.id,
                metadata={
                    "name": name,
                    "price": price,
                    "duration_days": duration_days,
                    "data_limit_gb": data_limit_gb,
                },
            )
            await session.flush()
            return plan

    async def deactivate_admin_plan(
        self,
        *,
        admin_telegram_id: int,
        plan_id: str,
    ) -> Plan:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            plan = await get_plan(session, plan_id=plan_id)
            if plan is None or plan.reseller_id != seller_bot.reseller_id:
                raise ValueError("plan_not_found")
            await set_plan_active(session, plan=plan, is_active=False)
            await record_audit_log(
                session,
                action="seller_plan.delete",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="plan",
                target_id=plan.id,
                metadata={"name": plan.name},
            )
            await session.flush()
            return plan

    async def get_pending_payment(
        self,
        *,
        admin_telegram_id: int,
        payment_id: str,
    ) -> PendingPayment:
        pending = await self.list_pending_payments(admin_telegram_id=admin_telegram_id)
        item = next((payment for payment in pending if payment.payment.id == payment_id), None)
        if item is None:
            raise ValueError("payment_not_found")
        return item

    async def approve_payment(
        self,
        *,
        admin_telegram_id: int,
        payment_id: str,
    ) -> ApprovedPayment:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            approved = await approve_payment(
                session,
                reseller_id=seller_bot.reseller_id,
                payment_id=payment_id,
                approved_by_telegram_id=admin_telegram_id,
            )
            if approved is None:
                raise ValueError("payment_not_found")
            payment, order = approved
            buyer = await session.get(Buyer, order.buyer_id)
            if buyer is None:
                raise ValueError("buyer_not_found")
            await record_audit_log(
                session,
                action="payment.approve",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="payment",
                target_id=payment.id,
                metadata={"order_id": order.id, "amount": float(payment.amount)},
            )
            await session.flush()
            return ApprovedPayment(payment=payment, order=order, buyer=buyer)

    async def reject_payment(
        self,
        *,
        admin_telegram_id: int,
        payment_id: str,
        reason: str,
    ) -> RejectedPayment:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("rejection_reason_required")
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            rejected = await reject_payment(
                session,
                reseller_id=seller_bot.reseller_id,
                payment_id=payment_id,
                rejected_by_telegram_id=admin_telegram_id,
                rejection_reason=normalized_reason[:500],
            )
            if rejected is None:
                raise ValueError("payment_not_found")
            payment, order = rejected
            buyer = await session.get(Buyer, order.buyer_id)
            if buyer is None:
                raise ValueError("buyer_not_found")
            await record_audit_log(
                session,
                action="payment.reject",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="payment",
                target_id=payment.id,
                metadata={
                    "order_id": order.id,
                    "amount": float(payment.amount),
                    "reason": payment.rejection_reason,
                },
            )
            await session.flush()
            return RejectedPayment(payment=payment, order=order, buyer=buyer)

    async def attach_payment_receipt(
        self,
        *,
        buyer_telegram_id: int,
        payment_id: str,
        file_id: str,
    ) -> Payment:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )
            from sqlalchemy import select

            result = await session.execute(
                select(Payment, Order)
                .join(Order, Payment.order_id == Order.id)
                .where(
                    Payment.id == payment_id,
                    Payment.reseller_id == seller_bot.reseller_id,
                    Payment.status == PaymentStatus.PENDING.value,
                    Order.buyer_id == buyer.id,
                )
            )
            row = result.one_or_none()
            if row is None:
                raise ValueError("payment_not_found")
            payment, _order = row
            payment.proof_file_id = file_id
            await session.flush()
            return payment

    async def list_buyer_services(self, *, buyer_telegram_id: int) -> list[VpnService]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            return await list_vpn_services_for_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )

    async def request_wallet_charge(
        self,
        *,
        buyer_telegram_id: int,
        amount: float,
    ) -> WalletChargeRequest:
        if amount <= 0:
            raise ValueError("invalid_amount")
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )
            transaction = await create_buyer_wallet_charge_request(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
                amount=amount,
                note="wallet charge payment request",
            )
            await session.flush()
            crypto_config = self._decrypt_crypto_gateway(
                await get_active_payment_gateway(
                    session,
                    reseller_id=seller_bot.reseller_id,
                    provider="crypto",
                )
            )
            if crypto_config is None:
                intent = self.payment_gateways.get("card_to_card").create_payment_intent(
                    amount=amount,
                    description=f"wallet_charge:{transaction.id}",
                    buyer_telegram_id=buyer_telegram_id,
                )
                instructions = intent.instructions
            else:
                instructions = self._crypto_payment_instructions(
                    config=crypto_config,
                    amount=amount,
                    reference=f"wallet_charge:{transaction.id}",
                )
            return WalletChargeRequest(transaction=transaction, instructions=instructions)

    async def list_buyer_wallet(self, *, buyer_telegram_id: int) -> BuyerWallet:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            buyer, transactions = await list_wallet_transactions_for_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )
            return BuyerWallet(buyer=buyer, transactions=transactions)

    async def get_buyer_wallet_transaction(
        self,
        *,
        buyer_telegram_id: int,
        transaction_id: str,
    ) -> WalletTransaction:
        wallet = await self.list_buyer_wallet(buyer_telegram_id=buyer_telegram_id)
        transaction = next((item for item in wallet.transactions if item.id == transaction_id), None)
        if transaction is None:
            raise ValueError("wallet_transaction_not_found")
        return transaction

    async def list_pending_wallet_charges(
        self,
        *,
        admin_telegram_id: int,
    ) -> list[WalletTransaction]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            return await list_pending_wallet_charges_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
            )

    async def approve_wallet_charge(
        self,
        *,
        admin_telegram_id: int,
        transaction_id: str,
    ) -> WalletChargeRequest:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            approved = await approve_buyer_wallet_charge(
                session,
                reseller_id=seller_bot.reseller_id,
                transaction_id=transaction_id,
                approved_by_telegram_id=admin_telegram_id,
            )
            if approved is None:
                raise ValueError("wallet_charge_not_found")
            transaction, _buyer = approved
            await record_audit_log(
                session,
                action="wallet_charge.approve",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="wallet_transaction",
                target_id=transaction.id,
                metadata={"amount": float(transaction.amount)},
            )
            await session.flush()
            return WalletChargeRequest(transaction=transaction, instructions="")

    async def attach_wallet_charge_receipt(
        self,
        *,
        buyer_telegram_id: int,
        transaction_id: str,
        file_id: str,
    ) -> WalletTransaction:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )
            from sqlalchemy import select

            result = await session.execute(
                select(WalletTransaction).where(
                    WalletTransaction.id == transaction_id,
                    WalletTransaction.reseller_id == seller_bot.reseller_id,
                    WalletTransaction.owner_type == WalletOwnerType.BUYER.value,
                    WalletTransaction.owner_id == buyer.id,
                    WalletTransaction.transaction_type == WalletTransactionType.CHARGE_REQUEST.value,
                    WalletTransaction.status == WalletTransactionStatus.PENDING.value,
                )
            )
            transaction = result.scalar_one_or_none()
            if transaction is None:
                raise ValueError("wallet_charge_not_found")
            transaction.proof_file_id = file_id
            await session.flush()
            return transaction

    @staticmethod
    def _ensure_reseller_admin(*, seller_bot: SellerBot, telegram_id: int) -> None:
        if seller_bot.reseller.telegram_user_id != telegram_id:
            raise PermissionError("not_reseller_admin")

    @staticmethod
    def _parse_support_contact(value: str | None) -> int | str | None:
        return SellerContextService._normalize_support_contact(value)

    @staticmethod
    def _normalize_support_contact(value: str | None) -> int | str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized.isdigit():
            support_telegram_id = int(normalized)
            return support_telegram_id if support_telegram_id > 0 else None
        username = normalized[1:] if normalized.startswith("@") else normalized
        if len(username) < 5 or len(username) > 32:
            return None
        if not all(char.isalnum() or char == "_" for char in username):
            return None
        return f"@{username}"

    def _decrypt_crypto_gateway(self, gateway: PaymentGateway | None) -> CryptoPaymentConfig | None:
        if gateway is None or gateway.config_encrypted is None or self.secret_box is None:
            return None
        raw_config = self.secret_box.decrypt(gateway.config_encrypted)
        if not raw_config:
            return None
        try:
            payload = json.loads(raw_config)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        currency = str(payload.get("currency") or "").strip()
        network = str(payload.get("network") or "").strip()
        wallet_address = str(payload.get("wallet_address") or "").strip()
        note = str(payload.get("note") or "").strip() or None
        if not currency or not network or not wallet_address:
            return None
        return CryptoPaymentConfig(
            currency=currency,
            network=network,
            wallet_address=wallet_address,
            note=note,
        )

    @staticmethod
    def _crypto_payment_instructions(
        *,
        config: CryptoPaymentConfig,
        amount: float,
        reference: str,
    ) -> str:
        lines = [
            "روش پرداخت: ارز دیجیتال",
            f"مبلغ سفارش: {amount:,.0f} تومان",
            f"ارز: {config.currency}",
            f"شبکه: {config.network}",
            "",
            "آدرس ولت:",
            config.wallet_address,
            "",
            f"شناسه پرداخت: {reference}",
            "بعد از پرداخت، هش تراکنش یا تصویر رسید را برای پشتیبانی ارسال کنید.",
        ]
        if config.note:
            lines.extend(["", f"توضیحات فروشنده: {config.note}"])
        return "\n".join(lines)

    async def open_ticket(
        self,
        *,
        buyer_telegram_id: int,
        subject: str,
        body: str,
    ) -> TicketThread:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )
            ticket, message = await create_ticket(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
                buyer_telegram_id=buyer_telegram_id,
                subject=subject[:160],
                body=body,
            )
            await session.flush()
            return TicketThread(ticket=ticket, messages=[message])

    async def reply_ticket_as_buyer(
        self,
        *,
        buyer_telegram_id: int,
        ticket_id: str,
        body: str,
    ) -> TicketThread:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            ticket = await get_ticket_for_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
                ticket_id=ticket_id,
            )
            if ticket is None:
                raise ValueError("ticket_not_found")
            await add_ticket_message(
                session,
                ticket=ticket,
                sender_type=TicketMessageSenderType.BUYER,
                sender_telegram_id=buyer_telegram_id,
                body=body,
            )
            await session.flush()
            return TicketThread(ticket=ticket, messages=await list_ticket_messages(session, ticket_id=ticket.id))

    async def reply_ticket_as_admin(
        self,
        *,
        admin_telegram_id: int,
        ticket_id: str,
        body: str,
    ) -> TicketThread:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            ticket = await get_ticket_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                ticket_id=ticket_id,
            )
            if ticket is None:
                raise ValueError("ticket_not_found")
            await add_ticket_message(
                session,
                ticket=ticket,
                sender_type=TicketMessageSenderType.ADMIN,
                sender_telegram_id=admin_telegram_id,
                body=body,
            )
            await record_audit_log(
                session,
                action="ticket.admin_reply",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="ticket",
                target_id=ticket.id,
            )
            await session.flush()
            return TicketThread(ticket=ticket, messages=await list_ticket_messages(session, ticket_id=ticket.id))

    async def list_my_tickets(self, *, buyer_telegram_id: int) -> list[Ticket]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            return await list_buyer_tickets(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )

    async def get_buyer_ticket_thread(
        self,
        *,
        buyer_telegram_id: int,
        ticket_id: str,
    ) -> TicketThread:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            ticket = await get_ticket_for_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
                ticket_id=ticket_id,
            )
            if ticket is None:
                raise ValueError("ticket_not_found")
            return TicketThread(
                ticket=ticket,
                messages=await list_ticket_messages(session, ticket_id=ticket.id),
            )

    async def list_open_tickets(self, *, admin_telegram_id: int) -> list[Ticket]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            return await list_open_tickets_for_reseller(session, reseller_id=seller_bot.reseller_id)

    async def get_admin_ticket_thread(
        self,
        *,
        admin_telegram_id: int,
        ticket_id: str,
    ) -> TicketThread:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            ticket = await get_ticket_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                ticket_id=ticket_id,
            )
            if ticket is None:
                raise ValueError("ticket_not_found")
            return TicketThread(
                ticket=ticket,
                messages=await list_ticket_messages(session, ticket_id=ticket.id),
            )

    async def close_ticket(self, *, admin_telegram_id: int, ticket_id: str) -> Ticket:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            ticket = await get_ticket_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                ticket_id=ticket_id,
            )
            if ticket is None:
                raise ValueError("ticket_not_found")
            await close_ticket(session, ticket=ticket)
            await record_audit_log(
                session,
                action="ticket.close",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="ticket",
                target_id=ticket.id,
            )
            await session.flush()
            return ticket

    async def create_broadcast(
        self,
        *,
        admin_telegram_id: int,
        title: str,
        body: str,
    ) -> BroadcastDraft:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            broadcast, recipients = await create_reseller_broadcast(
                session,
                reseller_id=seller_bot.reseller_id,
                title=title,
                body=body,
                created_by_telegram_id=admin_telegram_id,
            )
            await record_audit_log(
                session,
                action="broadcast.create_reseller",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="broadcast",
                target_id=broadcast.id,
                metadata={"target_count": len(recipients)},
            )
            await session.flush()
            return BroadcastDraft(broadcast=broadcast, recipients=recipients)

    async def get_broadcast_recipients(
        self,
        *,
        admin_telegram_id: int,
        broadcast_id: str,
    ) -> BroadcastDraft:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            broadcast = await get_broadcast_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                broadcast_id=broadcast_id,
            )
            if broadcast is None:
                raise ValueError("broadcast_not_found")
            recipients = await list_pending_broadcast_recipients(
                session,
                broadcast_id=broadcast.id,
            )
            return BroadcastDraft(broadcast=broadcast, recipients=recipients)

    async def mark_broadcast_sent(
        self,
        *,
        admin_telegram_id: int,
        broadcast_id: str,
        delivered_telegram_ids: set[int],
    ) -> Broadcast:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            broadcast = await get_broadcast_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                broadcast_id=broadcast_id,
            )
            if broadcast is None:
                raise ValueError("broadcast_not_found")
            recipients = await list_pending_broadcast_recipients(
                session,
                broadcast_id=broadcast.id,
            )
            delivered = [
                recipient
                for recipient in recipients
                if recipient.telegram_user_id in delivered_telegram_ids
            ]
            await mark_broadcast_sent(session, broadcast=broadcast, recipients=delivered)
            await session.flush()
            return broadcast

    async def sales_report(self, *, admin_telegram_id: int, days: int = 1) -> dict[str, float | int]:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            self._ensure_reseller_admin(seller_bot=seller_bot, telegram_id=admin_telegram_id)
            since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
            return await reseller_sales_report(session, reseller_id=seller_bot.reseller_id, since=since)
