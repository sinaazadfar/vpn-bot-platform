from __future__ import annotations

from sqlalchemy import select
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vpn_bot_platform.common.crypto import SecretBox, hash_secret
from vpn_bot_platform.common.models import (
    Buyer,
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    DiscountCode,
    DiscountType,
    MarzbanPanel,
    Order,
    OrderStatus,
    OrderType,
    Payment,
    PaymentStatus,
    PlatformSetting,
    Plan,
    PlanScope,
    Reseller,
    ResellerPanelAssignment,
    SettingScope,
    SellerBot,
    SellerBotStatus,
    TelegramUser,
    Ticket,
    TicketMessage,
    TicketMessageSenderType,
    TicketStatus,
    TrialGrant,
    utcnow,
    VpnService,
    WalletOwnerType,
    WalletTransaction,
    WalletTransactionStatus,
    WalletTransactionType,
)


async def upsert_telegram_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    language_code: str | None = None,
) -> TelegramUser:
    user = await session.get(TelegramUser, telegram_id)
    if user is None:
        user = TelegramUser(id=telegram_id)
        session.add(user)
    user.username = username
    user.first_name = first_name
    user.last_name = last_name
    user.language_code = language_code
    return user


async def create_reseller(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    display_name: str,
) -> Reseller:
    reseller = Reseller(telegram_user_id=telegram_user_id, display_name=display_name)
    session.add(reseller)
    return reseller


async def get_reseller_by_telegram_id(
    session: AsyncSession,
    *,
    telegram_id: int,
) -> Reseller | None:
    result = await session.execute(
        select(Reseller).where(Reseller.telegram_user_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def list_resellers(session: AsyncSession) -> list[Reseller]:
    result = await session.execute(select(Reseller).order_by(Reseller.created_at.desc()))
    return list(result.scalars().all())


async def create_marzban_panel(
    session: AsyncSession,
    *,
    name: str,
    base_url: str,
    secret_box: SecretBox,
    username: str | None = None,
    password: str | None = None,
    token: str | None = None,
) -> MarzbanPanel:
    panel = MarzbanPanel(
        name=name,
        base_url=base_url.rstrip("/"),
        username_encrypted=secret_box.encrypt(username),
        password_encrypted=secret_box.encrypt(password),
        token_encrypted=secret_box.encrypt(token),
    )
    session.add(panel)
    return panel


async def list_marzban_panels(session: AsyncSession) -> list[MarzbanPanel]:
    result = await session.execute(select(MarzbanPanel).order_by(MarzbanPanel.created_at.desc()))
    return list(result.scalars().all())


async def get_marzban_panel(session: AsyncSession, *, panel_id: str) -> MarzbanPanel | None:
    return await session.get(MarzbanPanel, panel_id)


async def assign_panel_to_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
    panel_id: str,
    marzban_admin_username: str | None = None,
) -> ResellerPanelAssignment:
    assignment = ResellerPanelAssignment(
        reseller_id=reseller_id,
        panel_id=panel_id,
        marzban_admin_username=marzban_admin_username,
    )
    session.add(assignment)
    return assignment


async def create_seller_bot(
    session: AsyncSession,
    *,
    reseller_id: str,
    name: str,
    token: str,
    secret_box: SecretBox,
) -> SellerBot:
    seller_bot = SellerBot(
        reseller_id=reseller_id,
        name=name,
        token_encrypted=secret_box.encrypt(token) or "",
        token_hash=hash_secret(token),
    )
    session.add(seller_bot)
    return seller_bot


async def get_seller_bot(session: AsyncSession, *, seller_bot_id: str) -> SellerBot | None:
    return await session.get(SellerBot, seller_bot_id)


async def get_seller_bot_with_reseller(
    session: AsyncSession,
    *,
    seller_bot_id: str,
) -> SellerBot | None:
    result = await session.execute(
        select(SellerBot)
        .options(selectinload(SellerBot.reseller))
        .where(SellerBot.id == seller_bot_id)
    )
    return result.scalar_one_or_none()


async def get_seller_bot_for_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
    seller_bot_id: str,
) -> SellerBot | None:
    result = await session.execute(
        select(SellerBot).where(
            SellerBot.id == seller_bot_id,
            SellerBot.reseller_id == reseller_id,
        )
    )
    return result.scalar_one_or_none()


async def list_seller_bots_by_status(
    session: AsyncSession,
    *,
    statuses: list[str],
) -> list[SellerBot]:
    result = await session.execute(
        select(SellerBot).where(SellerBot.status.in_(statuses)).order_by(SellerBot.created_at.asc())
    )
    return list(result.scalars().all())


async def update_seller_runtime_state(
    session: AsyncSession,
    *,
    seller_bot: SellerBot,
    status: SellerBotStatus,
    container_id: str | None = None,
    container_name: str | None = None,
    last_error: str | None = None,
) -> SellerBot:
    seller_bot.status = status.value
    seller_bot.container_id = container_id
    seller_bot.container_name = container_name
    seller_bot.last_error = last_error
    return seller_bot


async def get_buyer_by_telegram_id(
    session: AsyncSession,
    *,
    reseller_id: str,
    telegram_id: int,
) -> Buyer | None:
    result = await session.execute(
        select(Buyer).where(
            Buyer.reseller_id == reseller_id,
            Buyer.telegram_user_id == telegram_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_buyer(
    session: AsyncSession,
    *,
    reseller_id: str,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    language_code: str | None = None,
) -> Buyer:
    await upsert_telegram_user(
        session,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
    )
    buyer = await get_buyer_by_telegram_id(
        session,
        reseller_id=reseller_id,
        telegram_id=telegram_id,
    )
    if buyer is None:
        buyer = Buyer(reseller_id=reseller_id, telegram_user_id=telegram_id)
        session.add(buyer)
    return buyer


async def create_plan(
    session: AsyncSession,
    *,
    name: str,
    price: float,
    duration_days: int,
    data_limit_gb: int | None,
    reseller_id: str | None = None,
) -> Plan:
    plan = Plan(
        reseller_id=reseller_id,
        scope=PlanScope.RESELLER.value if reseller_id else PlanScope.GLOBAL.value,
        name=name,
        price=price,
        duration_days=duration_days,
        data_limit_gb=data_limit_gb,
    )
    session.add(plan)
    return plan


async def list_active_plans_for_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
) -> list[Plan]:
    result = await session.execute(
        select(Plan)
        .where(
            Plan.is_active.is_(True),
            (Plan.reseller_id == reseller_id) | (Plan.scope == PlanScope.GLOBAL.value),
        )
        .order_by(Plan.reseller_id.desc().nullslast(), Plan.price.asc(), Plan.created_at.asc())
    )
    return list(result.scalars().all())


async def list_all_plans(session: AsyncSession) -> list[Plan]:
    result = await session.execute(
        select(Plan).order_by(Plan.scope.asc(), Plan.price.asc(), Plan.created_at.asc())
    )
    return list(result.scalars().all())


async def get_active_plan_for_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
    plan_id: str,
) -> Plan | None:
    result = await session.execute(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.is_active.is_(True),
            (Plan.reseller_id == reseller_id) | (Plan.scope == PlanScope.GLOBAL.value),
        )
    )
    return result.scalar_one_or_none()


async def create_order_with_pending_payment(
    session: AsyncSession,
    *,
    reseller_id: str,
    buyer_id: str,
    plan_id: str,
    amount: float,
    payment_method: str = "card_to_card",
    order_type: OrderType = OrderType.NEW_SERVICE,
    target_service_id: str | None = None,
) -> tuple[Order, Payment]:
    order = Order(
        reseller_id=reseller_id,
        buyer_id=buyer_id,
        plan_id=plan_id,
        target_service_id=target_service_id,
        order_type=order_type.value,
        status=OrderStatus.WAITING_PAYMENT.value,
        total_amount=amount,
    )
    session.add(order)
    await session.flush()
    payment = Payment(
        reseller_id=reseller_id,
        order_id=order.id,
        status=PaymentStatus.PENDING.value,
        method=payment_method,
        amount=amount,
    )
    session.add(payment)
    return order, payment


async def create_discount_code(
    session: AsyncSession,
    *,
    code: str,
    discount_type: DiscountType,
    amount: float,
    max_uses: int | None = None,
    reseller_id: str | None = None,
) -> DiscountCode:
    discount = DiscountCode(
        reseller_id=reseller_id,
        code=code.upper(),
        discount_type=discount_type.value,
        amount=amount,
        max_uses=max_uses,
    )
    session.add(discount)
    return discount


async def get_active_discount_code(
    session: AsyncSession,
    *,
    reseller_id: str,
    code: str,
) -> DiscountCode | None:
    normalized = code.upper()
    result = await session.execute(
        select(DiscountCode)
        .where(
            DiscountCode.code == normalized,
            DiscountCode.is_active.is_(True),
            (DiscountCode.reseller_id == reseller_id) | (DiscountCode.reseller_id.is_(None)),
        )
        .order_by(DiscountCode.reseller_id.desc().nullslast())
    )
    discount = result.scalar_one_or_none()
    if discount is None:
        return None
    if discount.max_uses is not None and discount.used_count >= discount.max_uses:
        return None
    return discount


async def list_discount_codes(session: AsyncSession) -> list[DiscountCode]:
    result = await session.execute(
        select(DiscountCode).order_by(DiscountCode.created_at.desc())
    )
    return list(result.scalars().all())


def apply_discount_amount(*, price: float, discount: DiscountCode | None) -> float:
    if discount is None:
        return price
    if discount.discount_type == DiscountType.PERCENT.value:
        return max(0, price - (price * float(discount.amount) / 100))
    return max(0, price - float(discount.amount))


def increment_discount_usage(discount: DiscountCode | None) -> None:
    if discount is not None:
        discount.used_count += 1


async def list_pending_payments_for_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
) -> list[tuple[Payment, Order, Plan]]:
    result = await session.execute(
        select(Payment, Order, Plan)
        .join(Order, Payment.order_id == Order.id)
        .join(Plan, Order.plan_id == Plan.id)
        .where(
            Payment.reseller_id == reseller_id,
            Payment.status == PaymentStatus.PENDING.value,
            Order.status == OrderStatus.WAITING_PAYMENT.value,
        )
        .order_by(Payment.created_at.asc())
    )
    return list(result.all())


async def approve_payment(
    session: AsyncSession,
    *,
    reseller_id: str,
    payment_id: str,
    approved_by_telegram_id: int,
) -> tuple[Payment, Order] | None:
    result = await session.execute(
        select(Payment, Order)
        .join(Order, Payment.order_id == Order.id)
        .where(
            Payment.id == payment_id,
            Payment.reseller_id == reseller_id,
            Payment.status == PaymentStatus.PENDING.value,
            Order.status == OrderStatus.WAITING_PAYMENT.value,
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    payment, order = row
    payment.status = PaymentStatus.APPROVED.value
    payment.approved_by_telegram_id = approved_by_telegram_id
    order.status = OrderStatus.PROVISIONING.value
    return payment, order


async def get_provisioning_order_context(
    session: AsyncSession,
    *,
    reseller_id: str,
    order_id: str,
) -> tuple[Order, Buyer, Plan] | None:
    result = await session.execute(
        select(Order, Buyer, Plan)
        .join(Buyer, Order.buyer_id == Buyer.id)
        .join(Plan, Order.plan_id == Plan.id)
        .where(
            Order.id == order_id,
            Order.reseller_id == reseller_id,
            Order.status == OrderStatus.PROVISIONING.value,
        )
    )
    return result.one_or_none()


async def get_primary_panel_assignment(
    session: AsyncSession,
    *,
    reseller_id: str,
) -> tuple[ResellerPanelAssignment, MarzbanPanel] | None:
    result = await session.execute(
        select(ResellerPanelAssignment, MarzbanPanel)
        .join(MarzbanPanel, ResellerPanelAssignment.panel_id == MarzbanPanel.id)
        .where(
            ResellerPanelAssignment.reseller_id == reseller_id,
            MarzbanPanel.is_active.is_(True),
        )
        .order_by(ResellerPanelAssignment.created_at.asc())
    )
    return result.first()


async def create_vpn_service(
    session: AsyncSession,
    *,
    reseller_id: str,
    buyer_id: str,
    panel_id: str,
    marzban_username: str,
    subscription_url: str | None,
    data_limit_gb: int | None,
    expire_at,
) -> VpnService:
    service = VpnService(
        reseller_id=reseller_id,
        buyer_id=buyer_id,
        panel_id=panel_id,
        marzban_username=marzban_username,
        subscription_url=subscription_url,
        data_limit_gb=data_limit_gb,
        expire_at=expire_at,
    )
    session.add(service)
    return service


async def get_trial_grant(
    session: AsyncSession,
    *,
    reseller_id: str,
    buyer_id: str,
) -> TrialGrant | None:
    result = await session.execute(
        select(TrialGrant).where(
            TrialGrant.reseller_id == reseller_id,
            TrialGrant.buyer_id == buyer_id,
        )
    )
    return result.scalar_one_or_none()


async def create_trial_grant(
    session: AsyncSession,
    *,
    reseller_id: str,
    buyer_id: str,
    vpn_service_id: str | None = None,
) -> TrialGrant:
    grant = TrialGrant(
        reseller_id=reseller_id,
        buyer_id=buyer_id,
        vpn_service_id=vpn_service_id,
    )
    session.add(grant)
    return grant


async def list_vpn_services_for_buyer(
    session: AsyncSession,
    *,
    reseller_id: str,
    telegram_id: int,
) -> list[VpnService]:
    result = await session.execute(
        select(VpnService)
        .join(Buyer, VpnService.buyer_id == Buyer.id)
        .where(
            VpnService.reseller_id == reseller_id,
            Buyer.telegram_user_id == telegram_id,
        )
        .order_by(VpnService.created_at.desc())
    )
    return list(result.scalars().all())


async def get_vpn_service_for_buyer(
    session: AsyncSession,
    *,
    reseller_id: str,
    telegram_id: int,
    service_id: str,
) -> VpnService | None:
    result = await session.execute(
        select(VpnService)
        .join(Buyer, VpnService.buyer_id == Buyer.id)
        .where(
            VpnService.id == service_id,
            VpnService.reseller_id == reseller_id,
            Buyer.telegram_user_id == telegram_id,
        )
    )
    return result.scalar_one_or_none()


async def get_renewal_order_context(
    session: AsyncSession,
    *,
    reseller_id: str,
    order_id: str,
) -> tuple[Order, VpnService, Plan] | None:
    result = await session.execute(
        select(Order, VpnService, Plan)
        .join(VpnService, Order.target_service_id == VpnService.id)
        .join(Plan, Order.plan_id == Plan.id)
        .where(
            Order.id == order_id,
            Order.reseller_id == reseller_id,
            Order.order_type == OrderType.RENEWAL.value,
            Order.status == OrderStatus.PROVISIONING.value,
        )
    )
    return result.one_or_none()


async def mark_order_completed(session: AsyncSession, *, order: Order) -> Order:
    order.status = OrderStatus.COMPLETED.value
    return order


async def mark_order_failed(session: AsyncSession, *, order: Order) -> Order:
    order.status = OrderStatus.FAILED.value
    return order


async def create_buyer_wallet_charge_request(
    session: AsyncSession,
    *,
    reseller_id: str,
    buyer_id: str,
    amount: float,
    note: str | None = None,
) -> WalletTransaction:
    transaction = WalletTransaction(
        reseller_id=reseller_id,
        owner_type=WalletOwnerType.BUYER.value,
        owner_id=buyer_id,
        transaction_type=WalletTransactionType.CHARGE_REQUEST.value,
        status=WalletTransactionStatus.PENDING.value,
        amount=amount,
        note=note,
    )
    session.add(transaction)
    return transaction


async def list_pending_wallet_charges_for_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
) -> list[WalletTransaction]:
    result = await session.execute(
        select(WalletTransaction)
        .where(
            WalletTransaction.reseller_id == reseller_id,
            WalletTransaction.transaction_type == WalletTransactionType.CHARGE_REQUEST.value,
            WalletTransaction.status == WalletTransactionStatus.PENDING.value,
        )
        .order_by(WalletTransaction.created_at.asc())
    )
    return list(result.scalars().all())


async def approve_buyer_wallet_charge(
    session: AsyncSession,
    *,
    reseller_id: str,
    transaction_id: str,
    approved_by_telegram_id: int,
) -> tuple[WalletTransaction, Buyer] | None:
    result = await session.execute(
        select(WalletTransaction, Buyer)
        .join(Buyer, WalletTransaction.owner_id == Buyer.id)
        .where(
            WalletTransaction.id == transaction_id,
            WalletTransaction.reseller_id == reseller_id,
            WalletTransaction.owner_type == WalletOwnerType.BUYER.value,
            WalletTransaction.transaction_type == WalletTransactionType.CHARGE_REQUEST.value,
            WalletTransaction.status == WalletTransactionStatus.PENDING.value,
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    transaction, buyer = row
    transaction.status = WalletTransactionStatus.COMPLETED.value
    transaction.transaction_type = WalletTransactionType.CHARGE_APPROVED.value
    transaction.approved_by_telegram_id = approved_by_telegram_id
    buyer.wallet_balance = float(buyer.wallet_balance) + float(transaction.amount)
    return transaction, buyer


async def list_wallet_transactions_for_buyer(
    session: AsyncSession,
    *,
    reseller_id: str,
    telegram_id: int,
) -> tuple[Buyer | None, list[WalletTransaction]]:
    buyer = await get_buyer_by_telegram_id(
        session,
        reseller_id=reseller_id,
        telegram_id=telegram_id,
    )
    if buyer is None:
        return None, []
    result = await session.execute(
        select(WalletTransaction)
        .where(
            WalletTransaction.reseller_id == reseller_id,
            WalletTransaction.owner_type == WalletOwnerType.BUYER.value,
            WalletTransaction.owner_id == buyer.id,
        )
        .order_by(WalletTransaction.created_at.desc())
    )
    return buyer, list(result.scalars().all())


async def create_ticket(
    session: AsyncSession,
    *,
    reseller_id: str,
    buyer_id: str,
    buyer_telegram_id: int,
    subject: str,
    body: str,
) -> tuple[Ticket, TicketMessage]:
    ticket = Ticket(reseller_id=reseller_id, buyer_id=buyer_id, subject=subject)
    session.add(ticket)
    await session.flush()
    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type=TicketMessageSenderType.BUYER.value,
        sender_telegram_id=buyer_telegram_id,
        body=body,
    )
    session.add(message)
    return ticket, message


async def get_ticket_for_buyer(
    session: AsyncSession,
    *,
    reseller_id: str,
    telegram_id: int,
    ticket_id: str,
) -> Ticket | None:
    result = await session.execute(
        select(Ticket)
        .join(Buyer, Ticket.buyer_id == Buyer.id)
        .where(
            Ticket.id == ticket_id,
            Ticket.reseller_id == reseller_id,
            Buyer.telegram_user_id == telegram_id,
        )
    )
    return result.scalar_one_or_none()


async def get_ticket_for_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
    ticket_id: str,
) -> Ticket | None:
    result = await session.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.reseller_id == reseller_id)
    )
    return result.scalar_one_or_none()


async def add_ticket_message(
    session: AsyncSession,
    *,
    ticket: Ticket,
    sender_type: TicketMessageSenderType,
    sender_telegram_id: int,
    body: str,
) -> TicketMessage:
    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type=sender_type.value,
        sender_telegram_id=sender_telegram_id,
        body=body,
    )
    session.add(message)
    ticket.updated_at = utcnow()
    return message


async def list_buyer_tickets(
    session: AsyncSession,
    *,
    reseller_id: str,
    telegram_id: int,
) -> list[Ticket]:
    result = await session.execute(
        select(Ticket)
        .join(Buyer, Ticket.buyer_id == Buyer.id)
        .where(Ticket.reseller_id == reseller_id, Buyer.telegram_user_id == telegram_id)
        .order_by(Ticket.updated_at.desc())
    )
    return list(result.scalars().all())


async def list_open_tickets_for_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
) -> list[Ticket]:
    result = await session.execute(
        select(Ticket)
        .where(Ticket.reseller_id == reseller_id, Ticket.status == TicketStatus.OPEN.value)
        .order_by(Ticket.updated_at.desc())
    )
    return list(result.scalars().all())


async def list_ticket_messages(
    session: AsyncSession,
    *,
    ticket_id: str,
) -> list[TicketMessage]:
    result = await session.execute(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def close_ticket(session: AsyncSession, *, ticket: Ticket) -> Ticket:
    ticket.status = TicketStatus.CLOSED.value
    return ticket


async def create_reseller_broadcast(
    session: AsyncSession,
    *,
    reseller_id: str,
    title: str,
    body: str,
    created_by_telegram_id: int,
) -> tuple[Broadcast, list[BroadcastRecipient]]:
    buyers_result = await session.execute(
        select(Buyer).where(Buyer.reseller_id == reseller_id).order_by(Buyer.created_at.asc())
    )
    buyers = list(buyers_result.scalars().all())
    broadcast = Broadcast(
        reseller_id=reseller_id,
        title=title[:160],
        body=body,
        status=BroadcastStatus.DRAFT.value,
        target_count=len(buyers),
        created_by_telegram_id=created_by_telegram_id,
    )
    session.add(broadcast)
    await session.flush()
    recipients = [
        BroadcastRecipient(
            broadcast_id=broadcast.id,
            buyer_id=buyer.id,
            telegram_user_id=buyer.telegram_user_id,
        )
        for buyer in buyers
    ]
    session.add_all(recipients)
    return broadcast, recipients


async def get_broadcast_for_reseller(
    session: AsyncSession,
    *,
    reseller_id: str,
    broadcast_id: str,
) -> Broadcast | None:
    result = await session.execute(
        select(Broadcast).where(Broadcast.id == broadcast_id, Broadcast.reseller_id == reseller_id)
    )
    return result.scalar_one_or_none()


async def list_pending_broadcast_recipients(
    session: AsyncSession,
    *,
    broadcast_id: str,
) -> list[BroadcastRecipient]:
    result = await session.execute(
        select(BroadcastRecipient)
        .where(
            BroadcastRecipient.broadcast_id == broadcast_id,
            BroadcastRecipient.delivered_at.is_(None),
        )
        .order_by(BroadcastRecipient.telegram_user_id.asc())
    )
    return list(result.scalars().all())


async def mark_broadcast_sent(
    session: AsyncSession,
    *,
    broadcast: Broadcast,
    recipients: list[BroadcastRecipient],
) -> Broadcast:
    now = utcnow()
    for recipient in recipients:
        recipient.delivered_at = now
    broadcast.status = BroadcastStatus.SENT.value
    broadcast.sent_count = len(recipients)
    broadcast.sent_at = now
    return broadcast


async def create_global_broadcast(
    session: AsyncSession,
    *,
    title: str,
    body: str,
    created_by_telegram_id: int,
) -> tuple[Broadcast, list[BroadcastRecipient]]:
    buyers_result = await session.execute(select(Buyer).order_by(Buyer.created_at.asc()))
    buyers = list(buyers_result.scalars().all())
    broadcast = Broadcast(
        reseller_id=None,
        title=title[:160],
        body=body,
        status=BroadcastStatus.DRAFT.value,
        target_count=len(buyers),
        created_by_telegram_id=created_by_telegram_id,
    )
    session.add(broadcast)
    await session.flush()
    recipients = [
        BroadcastRecipient(
            broadcast_id=broadcast.id,
            buyer_id=buyer.id,
            telegram_user_id=buyer.telegram_user_id,
        )
        for buyer in buyers
    ]
    session.add_all(recipients)
    return broadcast, recipients


async def get_global_broadcast(
    session: AsyncSession,
    *,
    broadcast_id: str,
) -> Broadcast | None:
    result = await session.execute(
        select(Broadcast).where(Broadcast.id == broadcast_id, Broadcast.reseller_id.is_(None))
    )
    return result.scalar_one_or_none()


async def reseller_sales_report(
    session: AsyncSession,
    *,
    reseller_id: str,
    since,
) -> dict[str, float | int]:
    completed_orders = await session.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.reseller_id == reseller_id,
            Order.status == OrderStatus.COMPLETED.value,
            Order.created_at >= since,
        )
    )
    order_count, order_total = completed_orders.one()
    approved_payments = await session.execute(
        select(func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.reseller_id == reseller_id,
            Payment.status == PaymentStatus.APPROVED.value,
            Payment.created_at >= since,
        )
    )
    payment_count, payment_total = approved_payments.one()
    new_buyers = await session.execute(
        select(func.count(Buyer.id)).where(Buyer.reseller_id == reseller_id, Buyer.created_at >= since)
    )
    services = await session.execute(
        select(func.count(VpnService.id)).where(
            VpnService.reseller_id == reseller_id,
            VpnService.created_at >= since,
        )
    )
    wallet_charges = await session.execute(
        select(func.count(WalletTransaction.id), func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.reseller_id == reseller_id,
            WalletTransaction.status == WalletTransactionStatus.COMPLETED.value,
            WalletTransaction.transaction_type == WalletTransactionType.CHARGE_APPROVED.value,
            WalletTransaction.created_at >= since,
        )
    )
    wallet_count, wallet_total = wallet_charges.one()
    return {
        "completed_orders": int(order_count or 0),
        "completed_order_total": float(order_total or 0),
        "approved_payments": int(payment_count or 0),
        "approved_payment_total": float(payment_total or 0),
        "new_buyers": int(new_buyers.scalar_one() or 0),
        "new_services": int(services.scalar_one() or 0),
        "wallet_charges": int(wallet_count or 0),
        "wallet_charge_total": float(wallet_total or 0),
    }


async def global_sales_report(session: AsyncSession, *, since) -> dict[str, float | int]:
    completed_orders = await session.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status == OrderStatus.COMPLETED.value,
            Order.created_at >= since,
        )
    )
    order_count, order_total = completed_orders.one()
    resellers = await session.execute(select(func.count(Reseller.id)))
    buyers = await session.execute(select(func.count(Buyer.id)).where(Buyer.created_at >= since))
    services = await session.execute(select(func.count(VpnService.id)).where(VpnService.created_at >= since))
    return {
        "completed_orders": int(order_count or 0),
        "completed_order_total": float(order_total or 0),
        "resellers": int(resellers.scalar_one() or 0),
        "new_buyers": int(buyers.scalar_one() or 0),
        "new_services": int(services.scalar_one() or 0),
    }


async def set_global_setting(
    session: AsyncSession,
    *,
    key: str,
    value: str,
) -> PlatformSetting:
    result = await session.execute(
        select(PlatformSetting).where(
            PlatformSetting.scope == SettingScope.GLOBAL.value,
            PlatformSetting.scope_id.is_(None),
            PlatformSetting.key == key,
        )
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = PlatformSetting(
            scope=SettingScope.GLOBAL.value,
            scope_id=None,
            key=key,
            value=value,
        )
        session.add(setting)
    else:
        setting.value = value
    return setting


async def get_global_setting(
    session: AsyncSession,
    *,
    key: str,
) -> PlatformSetting | None:
    result = await session.execute(
        select(PlatformSetting).where(
            PlatformSetting.scope == SettingScope.GLOBAL.value,
            PlatformSetting.scope_id.is_(None),
            PlatformSetting.key == key,
        )
    )
    return result.scalar_one_or_none()
