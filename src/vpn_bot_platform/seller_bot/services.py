from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

from vpn_bot_platform.common.config import Settings
from vpn_bot_platform.common.db import session_scope
from vpn_bot_platform.common.models import (
    Buyer,
    Broadcast,
    BroadcastRecipient,
    Order,
    OrderType,
    Payment,
    Plan,
    Reseller,
    SellerBot,
    VpnService,
    WalletTransaction,
    Ticket,
    TicketMessage,
    TicketMessageSenderType,
)
from vpn_bot_platform.common.repositories import (
    approve_payment,
    approve_buyer_wallet_charge,
    add_ticket_message,
    close_ticket,
    apply_discount_amount,
    create_order_with_pending_payment,
    create_buyer_wallet_charge_request,
    create_ticket,
    create_reseller_broadcast,
    get_active_plan_for_reseller,
    get_active_discount_code,
    get_seller_bot_with_reseller,
    get_ticket_for_buyer,
    get_ticket_for_reseller,
    get_broadcast_for_reseller,
    get_vpn_service_for_buyer,
    list_pending_payments_for_reseller,
    list_pending_wallet_charges_for_reseller,
    list_buyer_tickets,
    list_open_tickets_for_reseller,
    list_ticket_messages,
    list_pending_broadcast_recipients,
    mark_broadcast_sent,
    reseller_sales_report,
    list_wallet_transactions_for_buyer,
    increment_discount_usage,
    list_vpn_services_for_buyer,
    list_active_plans_for_reseller,
    upsert_buyer,
)


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
class PendingPayment:
    payment: Payment
    order: Order
    plan: Plan


@dataclass(frozen=True)
class ApprovedPayment:
    payment: Payment
    order: Order


@dataclass(frozen=True)
class WalletChargeRequest:
    transaction: WalletTransaction
    instructions: str


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


class SellerContextService:
    def __init__(self, seller_bot_id: str, settings: Settings | None = None) -> None:
        self.seller_bot_id = seller_bot_id
        self.settings = settings

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

    async def list_plans(self) -> list[Plan]:
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
            )

    async def request_card_to_card_payment(
        self,
        *,
        buyer_telegram_id: int,
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
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
            )
            plan = await get_active_plan_for_reseller(
                session,
                reseller_id=seller_bot.reseller_id,
                plan_id=plan_id,
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
            )
            increment_discount_usage(discount)
            await session.flush()
            instructions = (
                self.settings.card_to_card_instructions
                if self.settings is not None
                else "Send the card-to-card receipt to support for approval."
            )
            return PaymentRequest(
                order=order,
                payment=payment,
                plan=plan,
                instructions=instructions,
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
            instructions = (
                self.settings.card_to_card_instructions
                if self.settings is not None
                else "Send the card-to-card receipt to support for approval."
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
            await session.flush()
            return ApprovedPayment(payment=payment, order=order)

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
                note="card_to_card wallet charge",
            )
            await session.flush()
            instructions = (
                self.settings.card_to_card_instructions
                if self.settings is not None
                else "Send the card-to-card receipt to support for approval."
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
            await session.flush()
            return WalletChargeRequest(transaction=transaction, instructions="")

    @staticmethod
    def _ensure_reseller_admin(*, seller_bot: SellerBot, telegram_id: int) -> None:
        if seller_bot.reseller.telegram_user_id != telegram_id:
            raise PermissionError("not_reseller_admin")

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
