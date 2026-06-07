from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from vpn_bot_platform.common.qr import make_qr_png_bytes
from vpn_bot_platform.common.ui.callbacks import parse_callback
from vpn_bot_platform.common.ui.keyboards import (
    admin_order_actions,
    admin_payment_actions,
    admin_ticket_actions,
    admin_wallet_charge_actions,
    confirm_keyboard,
    plan_buy_button,
    seller_admin_menu,
    seller_buyer_menu,
    seller_section_menu,
    service_actions,
    support_menu,
    wallet_charge_menu,
)
from vpn_bot_platform.common.ui.messages import section, short_id, status_label, title
from vpn_bot_platform.common.models import OrderType
from vpn_bot_platform.seller_bot.forced_join import missing_required_chats
from vpn_bot_platform.seller_bot.provisioning import ProvisioningService
from vpn_bot_platform.seller_bot.services import SellerContextService

router = Router(name="seller_basic")


class TicketCreateStates(StatesGroup):
    subject = State()
    body = State()
    confirm = State()


@router.message(CommandStart())
async def start(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext | None = None,
) -> None:
    if message.from_user is None:
        return
    if state is not None:
        await state.clear()
    if await _blocked_by_forced_join(message):
        return
    profile = await seller_context.register_buyer(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )
    await message.answer(
        _buyer_dashboard_text(seller_name=profile.seller_bot.name, reseller_name=profile.reseller.display_name),
        reply_markup=seller_buyer_menu(),
    )


@router.message(
    F.text.in_(
        {
            "Buy VPN",
            "My Services",
            "Wallet",
            "Support",
            "Trial",
            "Guides",
            "Pending Payments",
            "Wallet Charges",
            "Tickets",
            "Sales Report",
            "Buyer Home",
        }
    )
)
async def seller_reply_menu_alias(
    message: Message,
    seller_context: SellerContextService,
    provisioning_service: ProvisioningService,
) -> None:
    if message.from_user is None:
        return
    if message.text == "Buy VPN":
        await message.answer(await _plans_text(seller_context), reply_markup=seller_section_menu("plans"))
    elif message.text == "My Services":
        await message.answer(
            await _services_text(seller_context, buyer_telegram_id=message.from_user.id),
            reply_markup=seller_section_menu("services"),
        )
    elif message.text == "Wallet":
        await message.answer(
            await _wallet_text(seller_context, buyer_telegram_id=message.from_user.id),
            reply_markup=wallet_charge_menu(),
        )
    elif message.text == "Support":
        await message.answer(
            _guided_text(
                "Support",
                "Use the buttons below to see tickets or open a new one.",
                ["For a new ticket, send: /ticket <subject> | <message>"],
            ),
            reply_markup=support_menu(),
        )
    elif message.text == "Trial":
        await trial(message, provisioning_service)
    elif message.text == "Guides":
        await message.answer(
            _guided_text(
                "Connection Guides",
                "Use your subscription link in V2RayNG, Streisand, Hiddify, or Nekobox.",
                [],
            ),
            reply_markup=seller_section_menu("guides"),
        )
    elif message.text == "Pending Payments":
        await _send_admin_payments(message, seller_context)
    elif message.text == "Wallet Charges":
        await _send_admin_wallet(message, seller_context)
    elif message.text == "Tickets":
        await _send_admin_tickets(message, seller_context)
    elif message.text == "Sales Report":
        try:
            report = await seller_context.sales_report(admin_telegram_id=message.from_user.id, days=1)
        except PermissionError:
            await message.answer("You do not have reseller admin access.")
            return
        await message.answer(_format_report("Sales Report - Today", report), reply_markup=seller_admin_menu())
    elif message.text == "Buyer Home":
        await start(message, seller_context)


@router.callback_query(F.data.startswith("s:"))
async def seller_menu_callback(
    callback: CallbackQuery,
    state: FSMContext,
    seller_context: SellerContextService,
    provisioning_service: ProvisioningService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    action = parse_callback(callback.data or "")
    if action.action == "home":
        await state.clear()
        profile = await seller_context.register_buyer(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            language_code=callback.from_user.language_code,
        )
        await callback.message.edit_text(
            _buyer_dashboard_text(
                seller_name=profile.seller_bot.name,
                reseller_name=profile.reseller.display_name,
            ),
            reply_markup=seller_buyer_menu(),
        )
    elif action.action == "plans":
        await callback.message.edit_text(
            await _plans_text(seller_context),
            reply_markup=seller_section_menu("plans"),
        )
    elif action.action == "buy":
        if not action.value:
            await callback.answer("Plan is missing.", show_alert=True)
            return
        try:
            payment_request = await seller_context.request_card_to_card_payment(
                buyer_telegram_id=callback.from_user.id,
                plan_id=action.value,
            )
        except ValueError as exc:
            if str(exc) == "plan_not_found":
                await callback.answer("Plan not found.", show_alert=True)
                return
            raise
        await callback.message.edit_text(
            _payment_request_text(payment_request),
            reply_markup=seller_section_menu("plans"),
        )
    elif action.action == "services":
        await callback.message.edit_text(
            await _services_text(seller_context, buyer_telegram_id=callback.from_user.id),
            reply_markup=seller_section_menu("services"),
        )
    elif action.action == "service_qr":
        if not action.value:
            await callback.answer("Service is missing.", show_alert=True)
            return
        services = await seller_context.list_buyer_services(buyer_telegram_id=callback.from_user.id)
        service = next((item for item in services if item.id == action.value), None)
        if service is None or not service.subscription_url:
            await callback.answer("Subscription is not available.", show_alert=True)
            return
        qr_file = BufferedInputFile(
            make_qr_png_bytes(service.subscription_url),
            filename=f"{service.marzban_username}.png",
        )
        await callback.message.answer_photo(qr_file, caption=f"QR Code\nService: {service.id}")
    elif action.action == "service_sub":
        if not action.value:
            await callback.answer("Service is missing.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=action.value,
        )
        if service is None or not service.subscription_url:
            await callback.answer("Subscription is not available.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Subscription"),
                    f"Service: {service.marzban_username}",
                    f"Service ID: {service.id}",
                    "",
                    service.subscription_url,
                ]
            ),
            reply_markup=service_actions(service.id),
        )
    elif action.action == "renew":
        if not action.value:
            await callback.answer("Service is missing.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=action.value,
        )
        if service is None:
            await callback.answer("Service not found.", show_alert=True)
            return
        await callback.message.edit_text(
            await _renewal_text(seller_context, service_id=service.id),
            reply_markup=service_actions(service.id),
        )
    elif action.action == "wallet":
        await callback.message.edit_text(
            await _wallet_text(seller_context, buyer_telegram_id=callback.from_user.id),
            reply_markup=wallet_charge_menu(),
        )
    elif action.action == "wallet_add":
        if not action.value:
            await callback.answer("Amount is missing.", show_alert=True)
            return
        try:
            amount = float(action.value)
            charge = await seller_context.request_wallet_charge(
                buyer_telegram_id=callback.from_user.id,
                amount=amount,
            )
        except ValueError:
            await callback.answer("Invalid wallet charge.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Wallet Charge Request"),
                    f"Transaction ID: {charge.transaction.id}",
                    f"Amount: {charge.transaction.amount:,.0f}",
                    "",
                    charge.instructions,
                ]
            ),
            reply_markup=wallet_charge_menu(),
        )
    elif action.action == "wallet_custom":
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Custom Wallet Charge"),
                    "Send one message with the amount you want to charge:",
                    "",
                    "/charge_wallet <amount>",
                ]
            ),
            reply_markup=wallet_charge_menu(),
        )
    elif action.action == "trial":
        try:
            service = await provisioning_service.provision_trial(
                buyer_telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                language_code=callback.from_user.language_code,
            )
        except ValueError as exc:
            await callback.message.edit_text(
                _trial_error_text(str(exc)),
                reply_markup=seller_section_menu("trial"),
            )
        else:
            await callback.message.edit_text(
                _service_created_text("Trial VPN service created.", service),
                reply_markup=seller_section_menu("trial"),
            )
    elif action.action == "support":
        await callback.message.edit_text(
            _guided_text(
                "Support",
                "Use the buttons below to see tickets or open a new one.",
                ["For a new ticket, send: /ticket <subject> | <message>"],
            ),
            reply_markup=support_menu(),
        )
    elif action.action == "tickets":
        await callback.message.edit_text(
            await _buyer_tickets_text(seller_context, buyer_telegram_id=callback.from_user.id),
            reply_markup=support_menu(),
        )
    elif action.action == "ticket_open":
        await state.clear()
        await state.set_state(TicketCreateStates.subject)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Open Ticket"),
                    "Send the ticket subject.",
                    "",
                    "Example: Cannot connect on Android",
                ]
            ),
            reply_markup=support_menu(),
        )
    elif action.action == "ticket_create":
        data = await state.get_data()
        subject = str(data.get("ticket_subject") or "").strip()
        body = str(data.get("ticket_body") or "").strip()
        if not subject or not body:
            await callback.answer("Ticket draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            thread = await seller_context.open_ticket(
                buyer_telegram_id=callback.from_user.id,
                subject=subject,
                body=body,
            )
        except ValueError as exc:
            await callback.answer(f"Could not open ticket: {exc}", show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Ticket Opened"),
                    f"Ticket ID: {thread.ticket.id}",
                    f"Subject: {thread.ticket.subject}",
                    f"Status: {status_label(thread.ticket.status)}",
                ]
            ),
            reply_markup=support_menu(),
        )
    elif action.action == "ticket_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Ticket Canceled"), "No ticket was created."]),
            reply_markup=support_menu(),
        )
    elif action.action == "guides":
        await callback.message.edit_text(
            _guided_text(
                "Connection Guides",
                "Use your subscription link in V2RayNG, Streisand, Hiddify, or Nekobox.",
                [],
            ),
            reply_markup=seller_section_menu("guides"),
        )
    elif action.action == "admin":
        await _show_admin_dashboard(callback, seller_context)
    elif action.action == "admin_payments":
        await _show_admin_payments(callback, seller_context)
    elif action.action == "admin_wallet":
        await _show_admin_wallet(callback, seller_context)
    elif action.action == "admin_tickets":
        await _show_admin_tickets(callback, seller_context)
    elif action.action == "admin_report":
        try:
            report = await seller_context.sales_report(admin_telegram_id=callback.from_user.id, days=1)
        except PermissionError:
            await callback.answer("You do not have reseller admin access.", show_alert=True)
            return
        await callback.message.edit_text(
            _format_report("Sales Report - Today", report),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "admin_broadcast":
        await callback.message.edit_text(
            _guided_text(
                "Broadcast",
                "Create a broadcast draft, review it, then send it.",
                ["/broadcast <title> | <message>", "/send_broadcast <broadcast_id>"],
            ),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "pay_ok":
        if not action.value:
            await callback.answer("Payment is missing.", show_alert=True)
            return
        try:
            approved = await seller_context.approve_payment(
                admin_telegram_id=callback.from_user.id,
                payment_id=action.value,
            )
        except PermissionError:
            await callback.answer("You do not have reseller admin access.", show_alert=True)
            return
        except ValueError:
            await callback.answer("Pending payment not found.", show_alert=True)
            return
        is_renewal = approved.order.order_type == OrderType.RENEWAL.value
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Payment Approved"),
                    f"Payment ID: {approved.payment.id}",
                    f"Order ID: {approved.order.id}",
                    f"Order status: {status_label(approved.order.status)}",
                ]
            ),
            reply_markup=admin_order_actions(approved.order.id, renewal=is_renewal),
        )
    elif action.action == "provision_order":
        if not action.value:
            await callback.answer("Order is missing.", show_alert=True)
            return
        try:
            service = await provisioning_service.provision_order(
                admin_telegram_id=callback.from_user.id,
                order_id=action.value,
            )
        except PermissionError:
            await callback.answer("You do not have reseller admin access.", show_alert=True)
            return
        except ValueError as exc:
            await callback.answer(f"Could not provision: {exc}", show_alert=True)
            return
        await callback.message.edit_text(
            _service_created_text("VPN service provisioned.", service),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "apply_renewal":
        if not action.value:
            await callback.answer("Order is missing.", show_alert=True)
            return
        try:
            service = await provisioning_service.apply_renewal(
                admin_telegram_id=callback.from_user.id,
                order_id=action.value,
            )
        except PermissionError:
            await callback.answer("You do not have reseller admin access.", show_alert=True)
            return
        except ValueError as exc:
            await callback.answer(f"Could not renew: {exc}", show_alert=True)
            return
        await callback.message.edit_text(
            _service_created_text("VPN service renewed.", service),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "wallet_ok":
        if not action.value:
            await callback.answer("Transaction is missing.", show_alert=True)
            return
        try:
            approved = await seller_context.approve_wallet_charge(
                admin_telegram_id=callback.from_user.id,
                transaction_id=action.value,
            )
        except PermissionError:
            await callback.answer("You do not have reseller admin access.", show_alert=True)
            return
        except ValueError:
            await callback.answer("Pending wallet charge not found.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Wallet Charge Approved"),
                    f"Transaction ID: {approved.transaction.id}",
                    f"Amount: {approved.transaction.amount:,.0f}",
                ]
            ),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "ticket_close":
        if not action.value:
            await callback.answer("Ticket is missing.", show_alert=True)
            return
        try:
            ticket_item = await seller_context.close_ticket(
                admin_telegram_id=callback.from_user.id,
                ticket_id=action.value,
            )
        except PermissionError:
            await callback.answer("You do not have reseller admin access.", show_alert=True)
            return
        except ValueError:
            await callback.answer("Ticket not found.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Ticket Closed"),
                    f"Ticket ID: {ticket_item.id}",
                    f"Subject: {ticket_item.subject}",
                    f"Status: {status_label(ticket_item.status)}",
                ]
            ),
            reply_markup=seller_admin_menu(),
        )
    await callback.answer()


@router.message(TicketCreateStates.subject)
async def ticket_create_subject(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    subject = (message.text or "").strip()
    if not subject or subject.startswith("/"):
        await message.answer(
            "\n".join([title("Open Ticket"), "Send a short subject, not a command."]),
            reply_markup=support_menu(),
        )
        return
    await state.update_data(ticket_subject=subject[:160])
    await state.set_state(TicketCreateStates.body)
    await message.answer(
        "\n".join(
            [
                title("Open Ticket"),
                "Now send the message for support.",
                "",
                "Include device, app, and error details if possible.",
            ]
        ),
        reply_markup=support_menu(),
    )


@router.message(TicketCreateStates.body)
async def ticket_create_body(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    body = (message.text or "").strip()
    if not body or body.startswith("/"):
        await message.answer(
            "\n".join([title("Open Ticket"), "Send the support message, not a command."]),
            reply_markup=support_menu(),
        )
        return
    await state.update_data(ticket_body=body)
    await state.set_state(TicketCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Ticket"),
                f"Subject: {data.get('ticket_subject')}",
                "",
                str(data.get("ticket_body")),
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="s",
            confirm_action="ticket_create",
            cancel_action="ticket_cancel",
        ),
    )


@router.message(TicketCreateStates.confirm)
async def ticket_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Ticket"), "Use Confirm or Cancel below the preview."])
    )


async def _send_legacy_start(message: Message, seller_context: SellerContextService) -> None:
    profile = await seller_context.register_buyer(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )
    await message.answer(
        "\n".join(
            [
                f"Welcome to {profile.seller_bot.name}.",
                f"Seller: {profile.reseller.display_name}",
                "",
                "Available now:",
                "/start - open your buyer profile",
                "/plans - show available VPN plans",
                "/buy <plan_id> [coupon] - request card-to-card payment",
                "/renew <service_id> <plan_id> [coupon] - renew an existing service",
                "/my_services - show your VPN services",
                "/wallet - show wallet balance",
                "/charge_wallet <amount> - request wallet charge",
                "/trial - request a one-time trial",
                "/ticket <subject> | <message> - open support ticket",
                "/my_tickets - list your tickets",
                "/reply_ticket <ticket_id> <message>",
                "/admin - reseller admin panel",
                "",
                "Payment approval and provisioning are next.",
            ]
        )
    )


@router.message(Command("plans"))
async def plans(message: Message, seller_context: SellerContextService) -> None:
    if await _blocked_by_forced_join(message):
        return
    available_plans = await seller_context.list_plans()
    if not available_plans:
        await message.answer("No active plans are available yet.")
        return

    lines = ["Available plans:"]
    for plan in available_plans:
        traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
        lines.append(
            f"- {plan.name}: {plan.price:,.0f} | {plan.duration_days} days | {traffic} | id={plan.id}"
        )
    await message.answer("\n".join(lines))
    for plan in available_plans[:5]:
        await message.answer(
            f"{plan.name}\nAmount: {plan.price:,.0f}\nDuration: {plan.duration_days} days",
            reply_markup=plan_buy_button(plan.id),
        )


@router.message(Command("my_services"))
async def my_services(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    services = await seller_context.list_buyer_services(
        buyer_telegram_id=message.from_user.id,
    )
    if not services:
        await message.answer("You do not have any VPN services yet.")
        return

    lines = ["Your VPN services:"]
    for service in services:
        traffic = "Unlimited" if service.data_limit_gb is None else f"{service.data_limit_gb} GB"
        expire = service.expire_at.isoformat() if service.expire_at else "Unlimited"
        lines.extend(
            [
                f"- Username: {service.marzban_username}",
                f"  Traffic: {traffic}",
                f"  Expires: {expire}",
                f"  Status: {'active' if service.is_active else 'inactive'}",
                f"  Subscription: {service.subscription_url or '-'}",
            ]
        )
    await message.answer("\n".join(lines))
    await message.answer(
        "Service actions",
        reply_markup=service_actions(services[0].id),
    )


@router.message(Command("wallet"))
async def wallet(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    wallet_info = await seller_context.list_buyer_wallet(
        buyer_telegram_id=message.from_user.id,
    )
    balance = wallet_info.buyer.wallet_balance if wallet_info.buyer else 0
    lines = [f"Wallet balance: {balance:,.0f}", "", "Recent transactions:"]
    if not wallet_info.transactions:
        lines.append("- none")
    for transaction in wallet_info.transactions[:10]:
        lines.append(
            f"- {transaction.transaction_type} | {transaction.status} | {transaction.amount:,.0f}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("charge_wallet"))
async def charge_wallet(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    raw_amount = (command.args or "").strip()
    try:
        amount = float(raw_amount)
    except ValueError:
        await message.answer("Usage: /charge_wallet <amount>")
        return
    try:
        charge = await seller_context.request_wallet_charge(
            buyer_telegram_id=message.from_user.id,
            amount=amount,
        )
    except ValueError as exc:
        if str(exc) == "invalid_amount":
            await message.answer("Amount must be greater than zero.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "Wallet charge request created.",
                f"Transaction ID: {charge.transaction.id}",
                f"Amount: {charge.transaction.amount:,.0f}",
                "",
                charge.instructions,
            ]
        )
    )


@router.message(Command("trial"))
async def trial(
    message: Message,
    provisioning_service: ProvisioningService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    try:
        service = await provisioning_service.provision_trial(
            buyer_telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code,
        )
    except ValueError as exc:
        if str(exc) == "trial_disabled":
            await message.answer("Trial accounts are disabled right now.")
            return
        if str(exc) == "trial_already_used":
            await message.answer("You have already used your trial account.")
            return
        if str(exc) == "panel_assignment_not_found":
            await message.answer("Trial is not available because no panel is assigned.")
            return
        raise

    text = "\n".join(
        [
            "Trial VPN service created.",
            f"Service ID: {service.id}",
            f"Username: {service.marzban_username}",
            f"Traffic: {service.data_limit_gb} GB",
            f"Expires: {service.expire_at.isoformat() if service.expire_at else 'Unlimited'}",
            f"Subscription: {service.subscription_url or '-'}",
        ]
    )
    if not service.subscription_url:
        await message.answer(text)
        return
    qr_file = BufferedInputFile(
        make_qr_png_bytes(service.subscription_url),
        filename=f"{service.marzban_username}.png",
    )
    await message.answer_photo(qr_file, caption=text)


@router.message(Command("ticket"))
async def ticket(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    raw = (command.args or "").strip()
    if " | " not in raw:
        await message.answer("Usage: /ticket <subject> | <message>")
        return
    subject, body = [part.strip() for part in raw.split(" | ", maxsplit=1)]
    if not subject or not body:
        await message.answer("Usage: /ticket <subject> | <message>")
        return
    thread = await seller_context.open_ticket(
        buyer_telegram_id=message.from_user.id,
        subject=subject,
        body=body,
    )
    await message.answer(
        f"Ticket opened.\nTicket ID: {thread.ticket.id}\nSubject: {thread.ticket.subject}"
    )


@router.message(Command("my_tickets"))
async def my_tickets(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    tickets = await seller_context.list_my_tickets(buyer_telegram_id=message.from_user.id)
    if not tickets:
        await message.answer("You do not have any tickets.")
        return
    lines = ["Your tickets:"]
    for ticket_item in tickets:
        lines.append(f"- {ticket_item.id} | {ticket_item.status} | {ticket_item.subject}")
    await message.answer("\n".join(lines))


@router.message(Command("reply_ticket"))
async def reply_ticket(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) != 2:
        await message.answer("Usage: /reply_ticket <ticket_id> <message>")
        return
    try:
        thread = await seller_context.reply_ticket_as_buyer(
            buyer_telegram_id=message.from_user.id,
            ticket_id=args[0],
            body=args[1],
        )
    except ValueError as exc:
        if str(exc) == "ticket_not_found":
            await message.answer("Ticket not found.")
            return
        raise
    await message.answer(f"Reply added to ticket {thread.ticket.id}.")


@router.message(Command("buy"))
async def buy(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    args = (command.args or "").strip().split(maxsplit=1)
    if not args:
        await message.answer("Usage: /buy <plan_id> [coupon]")
        return

    try:
        payment_request = await seller_context.request_card_to_card_payment(
            buyer_telegram_id=message.from_user.id,
            plan_id=args[0],
            coupon_code=args[1] if len(args) == 2 else None,
        )
    except ValueError as exc:
        if str(exc) == "plan_not_found":
            await message.answer("Plan not found or inactive. Use /plans to see available plans.")
            return
        if str(exc) == "seller_bot_not_found":
            await message.answer("Seller bot is not registered correctly.")
            return
        if str(exc) == "discount_not_found":
            await message.answer("Coupon not found, inactive, or already used up.")
            return
        raise

    plan = payment_request.plan
    traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
    await message.answer(
        "\n".join(
            [
                "Payment request created.",
                f"Order ID: {payment_request.order.id}",
                f"Payment ID: {payment_request.payment.id}",
                f"Plan: {plan.name}",
                f"Amount: {payment_request.payment.amount:,.0f}",
                f"Duration: {plan.duration_days} days",
                f"Traffic: {traffic}",
                "",
                payment_request.instructions,
                "",
                "After payment approval, your VPN service will be provisioned.",
            ]
        )
    )


@router.message(Command("renew"))
async def renew(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    args = (command.args or "").strip().split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Usage: /renew <service_id> <plan_id> [coupon]")
        return
    try:
        payment_request = await seller_context.request_renewal_payment(
            buyer_telegram_id=message.from_user.id,
            service_id=args[0],
            plan_id=args[1],
            coupon_code=args[2] if len(args) == 3 else None,
        )
    except ValueError as exc:
        if str(exc) == "service_not_found":
            await message.answer("Service not found. Use /my_services to see your services.")
            return
        if str(exc) == "plan_not_found":
            await message.answer("Plan not found or inactive. Use /plans.")
            return
        if str(exc) == "discount_not_found":
            await message.answer("Coupon not found, inactive, or already used up.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "Renewal payment request created.",
                f"Order ID: {payment_request.order.id}",
                f"Payment ID: {payment_request.payment.id}",
                f"Plan: {payment_request.plan.name}",
                f"Amount: {payment_request.payment.amount:,.0f}",
                "",
                payment_request.instructions,
            ]
        )
    )


@router.message(Command("admin"))
async def admin(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    try:
        pending = await seller_context.list_pending_payments(
            admin_telegram_id=message.from_user.id,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return

    lines = [
        title("Reseller Admin"),
        "Choose an action from the buttons below.",
        "",
        "Pending payments:",
    ]
    if not pending:
        lines.append("- none")
    for item in pending:
        lines.append(
            f"- payment={item.payment.id} | order={item.order.id} | "
            f"plan={item.plan.name} | amount={item.payment.amount:,.0f}"
        )
    pending_wallet = await seller_context.list_pending_wallet_charges(
        admin_telegram_id=message.from_user.id,
    )
    lines.extend(["", "Pending wallet charges:"])
    if not pending_wallet:
        lines.append("- none")
    for item in pending_wallet:
        lines.append(f"- tx={item.id} | buyer={item.owner_id} | amount={item.amount:,.0f}")
    open_tickets = await seller_context.list_open_tickets(admin_telegram_id=message.from_user.id)
    lines.extend(["", "Open tickets:"])
    if not open_tickets:
        lines.append("- none")
    for ticket_item in open_tickets:
        lines.append(
            f"- ticket={ticket_item.id} | subject={ticket_item.subject} | status={ticket_item.status}"
        )
    await message.answer("\n".join(lines), reply_markup=seller_admin_menu())


@router.message(Command("approve_payment"))
async def approve_payment(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    payment_id = (command.args or "").strip()
    if not payment_id:
        await message.answer("Usage: /approve_payment <payment_id>")
        return
    try:
        approved = await seller_context.approve_payment(
            admin_telegram_id=message.from_user.id,
            payment_id=payment_id,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    except ValueError as exc:
        if str(exc) == "payment_not_found":
            await message.answer("Pending payment not found.")
            return
        raise

    await message.answer(
        "\n".join(
            [
                "Payment approved.",
                f"Payment ID: {approved.payment.id}",
                f"Order ID: {approved.order.id}",
                f"Order status: {approved.order.status}",
                "",
                "Provisioning is the next step.",
            ]
        )
    )


@router.message(Command("approve_wallet_charge"))
async def approve_wallet_charge(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    transaction_id = (command.args or "").strip()
    if not transaction_id:
        await message.answer("Usage: /approve_wallet_charge <transaction_id>")
        return
    try:
        approved = await seller_context.approve_wallet_charge(
            admin_telegram_id=message.from_user.id,
            transaction_id=transaction_id,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    except ValueError as exc:
        if str(exc) == "wallet_charge_not_found":
            await message.answer("Pending wallet charge not found.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "Wallet charge approved.",
                f"Transaction ID: {approved.transaction.id}",
                f"Amount: {approved.transaction.amount:,.0f}",
            ]
        )
    )


@router.message(Command("admin_reply_ticket"))
async def admin_reply_ticket(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) != 2:
        await message.answer("Usage: /admin_reply_ticket <ticket_id> <message>")
        return
    try:
        thread = await seller_context.reply_ticket_as_admin(
            admin_telegram_id=message.from_user.id,
            ticket_id=args[0],
            body=args[1],
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    except ValueError as exc:
        if str(exc) == "ticket_not_found":
            await message.answer("Ticket not found.")
            return
        raise
    await message.answer(f"Admin reply added to ticket {thread.ticket.id}.")


@router.message(Command("close_ticket"))
async def close_ticket(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    ticket_id = (command.args or "").strip()
    if not ticket_id:
        await message.answer("Usage: /close_ticket <ticket_id>")
        return
    try:
        closed = await seller_context.close_ticket(
            admin_telegram_id=message.from_user.id,
            ticket_id=ticket_id,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    except ValueError as exc:
        if str(exc) == "ticket_not_found":
            await message.answer("Ticket not found.")
            return
        raise
    await message.answer(f"Ticket closed.\nTicket ID: {closed.id}")


@router.message(Command("broadcast"))
async def broadcast(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    raw = (command.args or "").strip()
    if " | " not in raw:
        await message.answer("Usage: /broadcast <title> | <message>")
        return
    title, body = [part.strip() for part in raw.split(" | ", maxsplit=1)]
    if not title or not body:
        await message.answer("Usage: /broadcast <title> | <message>")
        return
    try:
        draft = await seller_context.create_broadcast(
            admin_telegram_id=message.from_user.id,
            title=title,
            body=body,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    await message.answer(
        "\n".join(
            [
                "Broadcast draft created.",
                f"Broadcast ID: {draft.broadcast.id}",
                f"Targets: {len(draft.recipients)}",
                f"Send with: /send_broadcast {draft.broadcast.id}",
            ]
        )
    )


@router.message(Command("send_broadcast"))
async def send_broadcast(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    broadcast_id = (command.args or "").strip()
    if not broadcast_id:
        await message.answer("Usage: /send_broadcast <broadcast_id>")
        return
    try:
        draft = await seller_context.get_broadcast_recipients(
            admin_telegram_id=message.from_user.id,
            broadcast_id=broadcast_id,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    except ValueError as exc:
        if str(exc) == "broadcast_not_found":
            await message.answer("Broadcast not found.")
            return
        raise

    delivered: set[int] = set()
    text = f"{draft.broadcast.title}\n\n{draft.broadcast.body}"
    for recipient in draft.recipients:
        try:
            await message.bot.send_message(recipient.telegram_user_id, text)
        except TelegramAPIError:
            continue
        delivered.add(recipient.telegram_user_id)
    sent = await seller_context.mark_broadcast_sent(
        admin_telegram_id=message.from_user.id,
        broadcast_id=draft.broadcast.id,
        delivered_telegram_ids=delivered,
    )
    await message.answer(
        f"Broadcast sent.\nDelivered: {sent.sent_count}/{sent.target_count}\nID: {sent.id}"
    )


@router.message(Command("sales_report"))
async def sales_report(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    days = _parse_days(command.args)
    try:
        report = await seller_context.sales_report(
            admin_telegram_id=message.from_user.id,
            days=days,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    await message.answer(_format_report(f"Sales report - last {days} day(s)", report))


def _parse_days(raw: str | None) -> int:
    if not raw:
        return 1
    try:
        days = int(raw.strip())
    except ValueError:
        return 1
    return max(1, min(days, 365))


def _buyer_dashboard_text(*, seller_name: str, reseller_name: str) -> str:
    return "\n".join(
        [
            title(seller_name),
            f"Seller: {reseller_name}",
            "",
            "Choose an action from the buttons below.",
        ]
    )


async def _plans_text(seller_context: SellerContextService) -> str:
    plans = await seller_context.list_plans()
    if not plans:
        return "\n".join([title("Buy VPN"), "No active plans are available yet."])
    rows = []
    for plan in plans[:12]:
        traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
        rows.append(
            f"- {plan.name} | {plan.price:,.0f} | {plan.duration_days} days | {traffic} | id={short_id(plan.id)}"
        )
    rows.extend(["", "Tap Buy on a plan message to start checkout."])
    return "\n".join([title("Buy VPN"), section("Available plans", rows)])


async def _services_text(seller_context: SellerContextService, *, buyer_telegram_id: int) -> str:
    services = await seller_context.list_buyer_services(buyer_telegram_id=buyer_telegram_id)
    if not services:
        return "\n".join([title("My Services"), "You do not have any VPN services yet."])
    rows = []
    for service in services[:12]:
        traffic = "Unlimited" if service.data_limit_gb is None else f"{service.data_limit_gb} GB"
        expire = service.expire_at.date().isoformat() if service.expire_at else "Unlimited"
        rows.append(
            f"- {service.marzban_username} | {status_label('active' if service.is_active else 'disabled')} | "
            f"{traffic} | expires={expire} | id={short_id(service.id)}"
        )
    rows.extend(["", "Tap a service action message for subscription, QR code, or renewal."])
    return "\n".join([title("My Services"), section("Services", rows)])


async def _find_buyer_service(
    seller_context: SellerContextService,
    *,
    buyer_telegram_id: int,
    service_id: str,
):
    services = await seller_context.list_buyer_services(buyer_telegram_id=buyer_telegram_id)
    return next((service for service in services if service.id == service_id), None)


async def _renewal_text(seller_context: SellerContextService, *, service_id: str) -> str:
    plans = await seller_context.list_plans()
    if not plans:
        return "\n".join([title("Renew Service"), "No active renewal plans are available."])
    rows = []
    for plan in plans[:12]:
        traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
        rows.append(
            f"- {plan.name} | {plan.price:,.0f} | {plan.duration_days} days | {traffic} | id={plan.id}"
        )
    rows.extend(["", f"To renew this service, send: /renew {service_id} <plan_id> [coupon]"])
    return "\n".join([title("Renew Service"), section("Plans", rows)])


async def _wallet_text(seller_context: SellerContextService, *, buyer_telegram_id: int) -> str:
    wallet_info = await seller_context.list_buyer_wallet(buyer_telegram_id=buyer_telegram_id)
    balance = wallet_info.buyer.wallet_balance if wallet_info.buyer else 0
    rows = [
        f"- {transaction.transaction_type} | {status_label(transaction.status)} | {transaction.amount:,.0f}"
        for transaction in wallet_info.transactions[:8]
    ]
    rows.extend(["", "Use the amount buttons below, or choose Custom."])
    return "\n".join([title("Wallet"), f"Balance: {balance:,.0f}", "", section("Recent transactions", rows)])


async def _buyer_tickets_text(
    seller_context: SellerContextService,
    *,
    buyer_telegram_id: int,
) -> str:
    tickets = await seller_context.list_my_tickets(buyer_telegram_id=buyer_telegram_id)
    rows = [
        f"- {ticket_item.id} | {status_label(ticket_item.status)} | {ticket_item.subject}"
        for ticket_item in tickets[:12]
    ]
    rows.extend(["", "Open tickets from the Support menu. To reply, send one message with ticket ID and text."])
    return "\n".join([title("My Tickets"), section("Tickets", rows)])


def _payment_request_text(payment_request) -> str:
    plan = payment_request.plan
    traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
    return "\n".join(
        [
            title("Payment Request"),
            f"Order ID: {payment_request.order.id}",
            f"Payment ID: {payment_request.payment.id}",
            f"Plan: {plan.name}",
            f"Amount: {payment_request.payment.amount:,.0f}",
            f"Duration: {plan.duration_days} days",
            f"Traffic: {traffic}",
            "",
            payment_request.instructions,
            "",
            "After approval, your VPN service will be provisioned.",
        ]
    )


def _service_created_text(header: str, service) -> str:
    return "\n".join(
        [
            title(header),
            f"Service ID: {service.id}",
            f"Username: {service.marzban_username}",
            f"Traffic: {service.data_limit_gb or 'Unlimited'} GB",
            f"Expires: {service.expire_at.isoformat() if service.expire_at else 'Unlimited'}",
            f"Subscription: {service.subscription_url or '-'}",
        ]
    )


def _trial_error_text(error: str) -> str:
    messages = {
        "trial_disabled": "Trial accounts are disabled right now.",
        "trial_already_used": "You have already used your trial account.",
        "panel_assignment_not_found": "Trial is not available because no panel is assigned.",
    }
    return "\n".join([title("Trial"), messages.get(error, "Trial is not available right now.")])


async def _show_admin_dashboard(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_payments(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("You do not have reseller admin access.", show_alert=True)
        return
    await callback.message.edit_text(
        "\n".join(
            [
                title("Reseller Admin"),
                f"Pending payments: {len(pending)}",
                "",
                "Choose an admin action below.",
            ]
        ),
        reply_markup=seller_admin_menu(),
    )


async def _show_admin_payments(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_payments(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("You do not have reseller admin access.", show_alert=True)
        return
    rows = [
        f"- payment={item.payment.id} | order={short_id(item.order.id)} | {item.payment.amount:,.0f}"
        for item in pending[:15]
    ]
    rows.extend(["", "Tap an approval button on a payment action card below."])
    await callback.message.edit_text(
        "\n".join([title("Pending Payments"), section("Payments", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in pending[:5]:
        await callback.message.answer(
            "\n".join(
                [
                    title("Payment Action"),
                    f"Payment ID: {item.payment.id}",
                    f"Order ID: {item.order.id}",
                    f"Plan: {item.plan.name}",
                    f"Amount: {item.payment.amount:,.0f}",
                ]
            ),
            reply_markup=admin_payment_actions(item.payment.id),
        )


async def _send_admin_payments(message: Message, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_payments(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    rows = [
        f"- payment={item.payment.id} | order={short_id(item.order.id)} | {item.payment.amount:,.0f}"
        for item in pending[:15]
    ]
    rows.extend(["", "Tap an approval button on a payment action card below."])
    await message.answer(
        "\n".join([title("Pending Payments"), section("Payments", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in pending[:5]:
        await message.answer(
            "\n".join(
                [
                    title("Payment Action"),
                    f"Payment ID: {item.payment.id}",
                    f"Order ID: {item.order.id}",
                    f"Plan: {item.plan.name}",
                    f"Amount: {item.payment.amount:,.0f}",
                ]
            ),
            reply_markup=admin_payment_actions(item.payment.id),
        )


async def _show_admin_wallet(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_wallet_charges(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("You do not have reseller admin access.", show_alert=True)
        return
    rows = [f"- tx={item.id} | amount={item.amount:,.0f}" for item in pending[:15]]
    rows.extend(["", "Tap an approval button on a wallet charge card below."])
    await callback.message.edit_text(
        "\n".join([title("Wallet Charges"), section("Pending charges", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in pending[:5]:
        await callback.message.answer(
            "\n".join(
                [
                    title("Wallet Charge Action"),
                    f"Transaction ID: {item.id}",
                    f"Buyer ID: {item.owner_id}",
                    f"Amount: {item.amount:,.0f}",
                ]
            ),
            reply_markup=admin_wallet_charge_actions(item.id),
        )


async def _send_admin_wallet(message: Message, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_wallet_charges(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    rows = [f"- tx={item.id} | amount={item.amount:,.0f}" for item in pending[:15]]
    rows.extend(["", "Tap an approval button on a wallet charge card below."])
    await message.answer(
        "\n".join([title("Wallet Charges"), section("Pending charges", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in pending[:5]:
        await message.answer(
            "\n".join(
                [
                    title("Wallet Charge Action"),
                    f"Transaction ID: {item.id}",
                    f"Buyer ID: {item.owner_id}",
                    f"Amount: {item.amount:,.0f}",
                ]
            ),
            reply_markup=admin_wallet_charge_actions(item.id),
        )


async def _show_admin_tickets(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        tickets = await seller_context.list_open_tickets(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("You do not have reseller admin access.", show_alert=True)
        return
    rows = [f"- ticket={item.id} | {item.subject}" for item in tickets[:15]]
    rows.extend(["", "Tap Close on a ticket card below, or reply by sending ticket ID and message."])
    await callback.message.edit_text(
        "\n".join([title("Open Tickets"), section("Tickets", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in tickets[:5]:
        await callback.message.answer(
            "\n".join(
                [
                    title("Ticket Action"),
                    f"Ticket ID: {item.id}",
                    f"Subject: {item.subject}",
                    f"Status: {status_label(item.status)}",
                ]
            ),
            reply_markup=admin_ticket_actions(item.id),
        )


async def _send_admin_tickets(message: Message, seller_context: SellerContextService) -> None:
    try:
        tickets = await seller_context.list_open_tickets(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    rows = [f"- ticket={item.id} | {item.subject}" for item in tickets[:15]]
    rows.extend(["", "Tap Close on a ticket card below, or reply by sending ticket ID and message."])
    await message.answer(
        "\n".join([title("Open Tickets"), section("Tickets", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in tickets[:5]:
        await message.answer(
            "\n".join(
                [
                    title("Ticket Action"),
                    f"Ticket ID: {item.id}",
                    f"Subject: {item.subject}",
                    f"Status: {status_label(item.status)}",
                ]
            ),
            reply_markup=admin_ticket_actions(item.id),
        )


def _format_report(title: str, report: dict[str, float | int]) -> str:
    lines = [title]
    for key, value in report.items():
        label = key.replace("_", " ").title()
        if isinstance(value, float):
            lines.append(f"{label}: {value:,.0f}")
        else:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _guided_text(name: str, description: str, examples: list[str]) -> str:
    rows = [title(name), description]
    if examples:
        rows.extend(["", "When text is required, send one message in this format:", *[f"- {item}" for item in examples]])
    return "\n".join(rows)


@router.message(Command("apply_renewal"))
async def apply_renewal(
    message: Message,
    command: CommandObject,
    provisioning_service: ProvisioningService,
) -> None:
    if message.from_user is None:
        return
    order_id = (command.args or "").strip()
    if not order_id:
        await message.answer("Usage: /apply_renewal <order_id>")
        return
    try:
        renewed = await provisioning_service.apply_renewal(
            admin_telegram_id=message.from_user.id,
            order_id=order_id,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    except ValueError as exc:
        if str(exc) == "renewal_not_ready":
            await message.answer("Renewal order is not ready.")
            return
        if str(exc) == "panel_not_found":
            await message.answer("Panel for this service is not available.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "VPN service renewed.",
                f"Order ID: {renewed.order.id}",
                f"Service ID: {renewed.vpn_service.id}",
                f"Username: {renewed.vpn_service.marzban_username}",
                f"New expiry: {renewed.vpn_service.expire_at.isoformat() if renewed.vpn_service.expire_at else 'Unlimited'}",
            ]
        )
    )


@router.message(Command("provision_order"))
async def provision_order(
    message: Message,
    command: CommandObject,
    provisioning_service: ProvisioningService,
) -> None:
    if message.from_user is None:
        return
    order_id = (command.args or "").strip()
    if not order_id:
        await message.answer("Usage: /provision_order <order_id>")
        return
    try:
        provisioned = await provisioning_service.provision_order(
            admin_telegram_id=message.from_user.id,
            order_id=order_id,
        )
    except PermissionError:
        await message.answer("You do not have reseller admin access.")
        return
    except ValueError as exc:
        if str(exc) == "order_not_ready":
            await message.answer("Order is not ready for provisioning.")
            return
        if str(exc) == "panel_assignment_not_found":
            await message.answer("No active Marzban panel is assigned to this reseller.")
            return
        raise

    subscription_url = provisioned.vpn_service.subscription_url
    text = "\n".join(
        [
            "VPN service provisioned.",
            f"Order ID: {provisioned.order.id}",
            f"Service ID: {provisioned.vpn_service.id}",
            f"Username: {provisioned.vpn_service.marzban_username}",
            f"Subscription: {subscription_url or '-'}",
        ]
    )
    if not subscription_url:
        await message.answer(text)
        return

    qr_file = BufferedInputFile(
        make_qr_png_bytes(subscription_url),
        filename=f"{provisioned.vpn_service.marzban_username}.png",
    )
    await message.answer_photo(qr_file, caption=text)


async def _blocked_by_forced_join(message: Message) -> bool:
    if message.from_user is None:
        return True
    missing = await missing_required_chats(message.bot, user_id=message.from_user.id)
    if not missing:
        return False
    lines = ["Please join required channel/group first:"]
    for chat in missing:
        lines.append(f"- {chat.title or chat.chat_id}")
    await message.answer("\n".join(lines))
    return True
