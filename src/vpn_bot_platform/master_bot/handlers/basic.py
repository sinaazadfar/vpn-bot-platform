from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from vpn_bot_platform.common.models import DiscountType, ResellerStatus
from vpn_bot_platform.common.forced_join import ForcedJoinChat
from vpn_bot_platform.master_bot.services.resellers import ResellerService

router = Router(name="master_basic")


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "\n".join(
            [
                "Master bot is running.",
                "",
                "Commands:",
                "/admin - show owner menu",
                "/add_reseller <telegram_id> <display_name>",
                "/rename_reseller <telegram_id> <display_name>",
                "/set_reseller_status <telegram_id> <active|suspended|disabled>",
                "/disable_reseller <telegram_id>",
                "/list_resellers",
                "/add_seller_bot <reseller_telegram_id> <bot_name> <bot_token>",
                "/add_panel_token <name> <base_url> <token>",
                "/add_panel_password <name> <base_url> <username> <password>",
                "/list_panels",
                "/assign_panel <reseller_telegram_id> <panel_id> [marzban_admin_username]",
                "/start_seller <seller_bot_id>",
                "/stop_seller <seller_bot_id>",
                "/seller_health <seller_bot_id>",
                "/seller_logs <seller_bot_id>",
                "/add_global_plan <name> <price> <duration_days> <data_limit_gb|unlimited>",
                "/add_reseller_plan <reseller_telegram_id> <name> <price> <duration_days> <data_limit_gb|unlimited>",
                "/list_plans",
                "/add_discount <code> <percent|fixed> <amount> [max_uses]",
                "/list_discounts",
                "/global_broadcast <title> | <message>",
                "/send_global_broadcast <broadcast_id>",
                "/global_report [days]",
                "/set_forced_join <chat_id> [title]",
                "/list_forced_join",
            ]
        )
    )


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    await message.answer(
        "\n".join(
            [
                "Owner menu",
                "",
                "Phase 2 MVP commands:",
                "/add_reseller <telegram_id> <display_name>",
                "/rename_reseller <telegram_id> <display_name>",
                "/set_reseller_status <telegram_id> <active|suspended|disabled>",
                "/disable_reseller <telegram_id>",
                "/list_resellers",
                "/add_seller_bot <reseller_telegram_id> <bot_name> <bot_token>",
                "/add_panel_token <name> <base_url> <token>",
                "/add_panel_password <name> <base_url> <username> <password>",
                "/list_panels",
                "/assign_panel <reseller_telegram_id> <panel_id> [marzban_admin_username]",
                "/start_seller <seller_bot_id>",
                "/stop_seller <seller_bot_id>",
                "/seller_health <seller_bot_id>",
                "/seller_logs <seller_bot_id>",
                "/add_global_plan <name> <price> <duration_days> <data_limit_gb|unlimited>",
                "/add_reseller_plan <reseller_telegram_id> <name> <price> <duration_days> <data_limit_gb|unlimited>",
                "/list_plans",
                "/add_discount <code> <percent|fixed> <amount> [max_uses]",
                "/list_discounts",
                "/global_broadcast <title> | <message>",
                "/send_global_broadcast <broadcast_id>",
                "/global_report [days]",
                "/set_forced_join <chat_id> [title]",
                "/list_forced_join",
            ]
        )
    )


@router.message(Command("add_reseller"))
async def add_reseller(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) != 2 or not args[0].isdigit():
        await message.answer("Usage: /add_reseller <telegram_id> <display_name>")
        return

    registered = await reseller_service.register_reseller(
        telegram_id=int(args[0]),
        display_name=args[1].strip(),
    )
    status = "already existed" if registered.existed else "created"
    await message.answer(
        f"Reseller {status}.\nID: {registered.reseller.id}\nName: {registered.reseller.display_name}"
    )


@router.message(Command("rename_reseller"))
async def rename_reseller(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) != 2 or not args[0].isdigit():
        await message.answer("Usage: /rename_reseller <telegram_id> <display_name>")
        return
    try:
        reseller = await reseller_service.rename_reseller(
            reseller_telegram_id=int(args[0]),
            display_name=args[1].strip(),
            actor_telegram_id=message.from_user.id if message.from_user else None,
        )
    except ValueError as exc:
        if str(exc) == "reseller_not_found":
            await message.answer("Reseller not found.")
            return
        raise
    await message.answer(
        f"Reseller renamed.\nID: {reseller.id}\nName: {reseller.display_name}\nStatus: {reseller.status}"
    )


@router.message(Command("set_reseller_status"))
async def set_reseller_status(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) != 2 or not args[0].isdigit():
        await message.answer("Usage: /set_reseller_status <telegram_id> <active|suspended|disabled>")
        return
    try:
        status = ResellerStatus(args[1].strip())
    except ValueError:
        await message.answer("Status must be active, suspended, or disabled.")
        return
    try:
        reseller = await reseller_service.set_reseller_status(
            reseller_telegram_id=int(args[0]),
            status=status,
            actor_telegram_id=message.from_user.id if message.from_user else None,
        )
    except ValueError as exc:
        if str(exc) == "reseller_not_found":
            await message.answer("Reseller not found.")
            return
        raise
    await message.answer(
        f"Reseller status updated.\nID: {reseller.id}\nName: {reseller.display_name}\nStatus: {reseller.status}"
    )


@router.message(Command("disable_reseller"))
async def disable_reseller(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    telegram_id = (command.args or "").strip()
    if not telegram_id.isdigit():
        await message.answer("Usage: /disable_reseller <telegram_id>")
        return
    try:
        reseller = await reseller_service.set_reseller_status(
            reseller_telegram_id=int(telegram_id),
            status=ResellerStatus.DISABLED,
            actor_telegram_id=message.from_user.id if message.from_user else None,
        )
    except ValueError as exc:
        if str(exc) == "reseller_not_found":
            await message.answer("Reseller not found.")
            return
        raise
    await message.answer(
        f"Reseller disabled.\nID: {reseller.id}\nName: {reseller.display_name}"
    )


@router.message(Command("list_resellers"))
async def list_resellers(message: Message, reseller_service: ResellerService) -> None:
    resellers = await reseller_service.list_resellers()
    if not resellers:
        await message.answer("No resellers registered yet.")
        return

    lines = ["Resellers:"]
    for reseller in resellers:
        lines.append(
            f"- {reseller.display_name} | tg={reseller.telegram_user_id} | status={reseller.status}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("add_seller_bot"))
async def add_seller_bot(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=2)
    if len(args) != 3 or not args[0].isdigit():
        await message.answer("Usage: /add_seller_bot <reseller_telegram_id> <bot_name> <bot_token>")
        return

    try:
        seller_bot = await reseller_service.register_seller_bot(
            reseller_telegram_id=int(args[0]),
            bot_name=args[1].strip(),
            bot_token=args[2].strip(),
        )
    except ValueError as exc:
        if str(exc) == "reseller_not_found":
            await message.answer("Reseller not found. Add reseller first.")
            return
        raise

    await message.answer(
        "\n".join(
            [
                "Seller bot registered.",
                f"ID: {seller_bot.id}",
                f"Name: {seller_bot.name}",
                f"Status: {seller_bot.status}",
            ]
        )
    )


@router.message(Command("add_panel_token"))
async def add_panel_token(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=2)
    if len(args) != 3:
        await message.answer("Usage: /add_panel_token <name> <base_url> <token>")
        return

    panel = await reseller_service.register_marzban_panel(
        name=args[0].strip(),
        base_url=args[1].strip(),
        token=args[2].strip(),
    )
    await message.answer(f"Panel registered.\nID: {panel.id}\nName: {panel.name}")


@router.message(Command("add_panel_password"))
async def add_panel_password(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=3)
    if len(args) != 4:
        await message.answer("Usage: /add_panel_password <name> <base_url> <username> <password>")
        return

    panel = await reseller_service.register_marzban_panel(
        name=args[0].strip(),
        base_url=args[1].strip(),
        username=args[2].strip(),
        password=args[3].strip(),
    )
    await message.answer(f"Panel registered.\nID: {panel.id}\nName: {panel.name}")


@router.message(Command("list_panels"))
async def list_panels(message: Message, reseller_service: ResellerService) -> None:
    panels = await reseller_service.list_marzban_panels()
    if not panels:
        await message.answer("No Marzban panels registered yet.")
        return

    lines = ["Marzban panels:"]
    for panel in panels:
        lines.append(f"- {panel.name} | id={panel.id} | url={panel.base_url}")
    await message.answer("\n".join(lines))


@router.message(Command("assign_panel"))
async def assign_panel(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=2)
    if len(args) < 2 or not args[0].isdigit():
        await message.answer("Usage: /assign_panel <reseller_telegram_id> <panel_id> [marzban_admin_username]")
        return

    try:
        assignment = await reseller_service.assign_panel(
            reseller_telegram_id=int(args[0]),
            panel_id=args[1].strip(),
            marzban_admin_username=args[2].strip() if len(args) == 3 else None,
        )
    except ValueError as exc:
        if str(exc) == "reseller_not_found":
            await message.answer("Reseller not found.")
            return
        if str(exc) == "panel_not_found":
            await message.answer("Panel not found.")
            return
        raise

    await message.answer(
        "\n".join(
            [
                "Panel assigned.",
                f"Assignment ID: {assignment.id}",
                f"Reseller ID: {assignment.reseller_id}",
                f"Panel ID: {assignment.panel_id}",
            ]
        )
    )


@router.message(Command("start_seller"))
async def start_seller(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    seller_bot_id = (command.args or "").strip()
    if not seller_bot_id:
        await message.answer("Usage: /start_seller <seller_bot_id>")
        return

    try:
        seller_bot = await reseller_service.start_seller_bot(seller_bot_id=seller_bot_id)
    except ValueError as exc:
        if str(exc) == "seller_bot_not_found":
            await message.answer("Seller bot not found.")
            return
        if str(exc) == "seller_token_unavailable":
            await message.answer("Seller token cannot be decrypted.")
            return
        raise
    except RuntimeError as exc:
        await message.answer(f"Could not start seller bot: {exc}")
        return

    await message.answer(
        "\n".join(
            [
                "Seller bot started.",
                f"ID: {seller_bot.id}",
                f"Container: {seller_bot.container_name}",
                f"Status: {seller_bot.status}",
            ]
        )
    )


@router.message(Command("stop_seller"))
async def stop_seller(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    seller_bot_id = (command.args or "").strip()
    if not seller_bot_id:
        await message.answer("Usage: /stop_seller <seller_bot_id>")
        return

    try:
        seller_bot = await reseller_service.stop_seller_bot(seller_bot_id=seller_bot_id)
    except ValueError as exc:
        if str(exc) == "seller_bot_not_found":
            await message.answer("Seller bot not found.")
            return
        raise

    await message.answer(
        "\n".join(
            [
                "Seller bot stopped.",
                f"ID: {seller_bot.id}",
                f"Container: {seller_bot.container_name or '-'}",
                f"Status: {seller_bot.status}",
            ]
        )
    )


@router.message(Command("seller_health"))
async def seller_health(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    seller_bot_id = (command.args or "").strip()
    if not seller_bot_id:
        await message.answer("Usage: /seller_health <seller_bot_id>")
        return

    try:
        status = await reseller_service.seller_health(seller_bot_id=seller_bot_id)
    except ValueError as exc:
        if str(exc) == "seller_bot_not_found":
            await message.answer("Seller bot not found.")
            return
        raise

    await message.answer(
        "\n".join(
            [
                "Seller bot health",
                f"ID: {status.seller_bot.id}",
                f"Status: {status.seller_bot.status}",
                f"Container: {status.seller_bot.container_name or '-'}",
                f"Health: {status.health}",
                f"Last error: {status.seller_bot.last_error or '-'}",
            ]
        )
    )


@router.message(Command("seller_logs"))
async def seller_logs(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    seller_bot_id = (command.args or "").strip()
    if not seller_bot_id:
        await message.answer("Usage: /seller_logs <seller_bot_id>")
        return

    try:
        status = await reseller_service.seller_logs(seller_bot_id=seller_bot_id)
    except ValueError as exc:
        if str(exc) == "seller_bot_not_found":
            await message.answer("Seller bot not found.")
            return
        raise

    logs = (status.logs or "").strip() or "(no logs)"
    await message.answer(
        "\n".join(
            [
                f"Seller bot logs | health={status.health}",
                f"ID: {status.seller_bot.id}",
                "",
                _telegram_code_block(logs[-3500:]),
            ]
        )
    )


def _telegram_code_block(value: str) -> str:
    escaped = value.replace("```", "`\u200b``")
    return f"```\n{escaped}\n```"


@router.message(Command("add_global_plan"))
async def add_global_plan(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=3)
    if len(args) != 4:
        await message.answer("Usage: /add_global_plan <name> <price> <duration_days> <data_limit_gb|unlimited>")
        return
    parsed = _parse_plan_args(args[1:])
    if parsed is None:
        await message.answer("Price, duration, and data limit must be valid numbers. Use unlimited for no data limit.")
        return
    price, duration_days, data_limit_gb = parsed
    plan = await reseller_service.create_global_plan(
        name=args[0].strip(),
        price=price,
        duration_days=duration_days,
        data_limit_gb=data_limit_gb,
    )
    await message.answer(f"Global plan created.\nID: {plan.id}\nName: {plan.name}")


@router.message(Command("add_reseller_plan"))
async def add_reseller_plan(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=4)
    if len(args) != 5 or not args[0].isdigit():
        await message.answer("Usage: /add_reseller_plan <reseller_telegram_id> <name> <price> <duration_days> <data_limit_gb|unlimited>")
        return
    parsed = _parse_plan_args(args[2:])
    if parsed is None:
        await message.answer("Price, duration, and data limit must be valid numbers. Use unlimited for no data limit.")
        return
    price, duration_days, data_limit_gb = parsed
    try:
        plan = await reseller_service.create_reseller_plan(
            reseller_telegram_id=int(args[0]),
            name=args[1].strip(),
            price=price,
            duration_days=duration_days,
            data_limit_gb=data_limit_gb,
        )
    except ValueError as exc:
        if str(exc) == "reseller_not_found":
            await message.answer("Reseller not found.")
            return
        raise
    await message.answer(f"Reseller plan created.\nID: {plan.id}\nName: {plan.name}")


@router.message(Command("list_plans"))
async def list_plans(message: Message, reseller_service: ResellerService) -> None:
    plans = await reseller_service.list_plans()
    if not plans:
        await message.answer("No plans created yet.")
        return
    lines = ["Plans:"]
    for plan in plans:
        traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
        owner = "global" if plan.reseller_id is None else f"reseller={plan.reseller_id}"
        lines.append(f"- {plan.name} | {owner} | {plan.price:,.0f} | {plan.duration_days} days | {traffic} | id={plan.id}")
    await message.answer("\n".join(lines))


def _parse_plan_args(args: list[str]) -> tuple[float, int, int | None] | None:
    if len(args) != 3:
        return None
    try:
        price = float(args[0])
        duration_days = int(args[1])
        data_limit_gb = None if args[2].lower() == "unlimited" else int(args[2])
    except ValueError:
        return None
    if price < 0 or duration_days <= 0 or (data_limit_gb is not None and data_limit_gb <= 0):
        return None
    return price, duration_days, data_limit_gb


@router.message(Command("add_discount"))
async def add_discount(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=3)
    if len(args) < 3:
        await message.answer("Usage: /add_discount <code> <percent|fixed> <amount> [max_uses]")
        return
    if args[1] not in {DiscountType.PERCENT.value, DiscountType.FIXED.value}:
        await message.answer("Discount type must be percent or fixed.")
        return
    try:
        amount = float(args[2])
        max_uses = int(args[3]) if len(args) == 4 else None
    except ValueError:
        await message.answer("Amount and max_uses must be valid numbers.")
        return
    if amount <= 0 or (args[1] == DiscountType.PERCENT.value and amount > 100):
        await message.answer("Discount amount is invalid.")
        return
    discount = await reseller_service.create_global_discount(
        code=args[0],
        discount_type=DiscountType(args[1]),
        amount=amount,
        max_uses=max_uses,
    )
    await message.answer(
        f"Discount created.\nCode: {discount.code}\nType: {discount.discount_type}\nAmount: {discount.amount}"
    )


@router.message(Command("list_discounts"))
async def list_discounts(message: Message, reseller_service: ResellerService) -> None:
    discounts = await reseller_service.list_discounts()
    if not discounts:
        await message.answer("No discounts created yet.")
        return
    lines = ["Discounts:"]
    for discount in discounts:
        scope = "global" if discount.reseller_id is None else f"reseller={discount.reseller_id}"
        limit = "unlimited" if discount.max_uses is None else str(discount.max_uses)
        lines.append(
            f"- {discount.code} | {scope} | {discount.discount_type} {discount.amount} | "
            f"used={discount.used_count}/{limit} | active={discount.is_active}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("global_broadcast"))
async def global_broadcast(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    if message.from_user is None:
        return
    raw = (command.args or "").strip()
    if " | " not in raw:
        await message.answer("Usage: /global_broadcast <title> | <message>")
        return
    title, body = [part.strip() for part in raw.split(" | ", maxsplit=1)]
    if not title or not body:
        await message.answer("Usage: /global_broadcast <title> | <message>")
        return
    draft = await reseller_service.create_global_broadcast(
        admin_telegram_id=message.from_user.id,
        title=title,
        body=body,
    )
    await message.answer(
        "\n".join(
            [
                "Global broadcast draft created.",
                f"Broadcast ID: {draft.broadcast.id}",
                f"Targets: {len(draft.recipients)}",
                f"Send with: /send_global_broadcast {draft.broadcast.id}",
            ]
        )
    )


@router.message(Command("send_global_broadcast"))
async def send_global_broadcast(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    broadcast_id = (command.args or "").strip()
    if not broadcast_id:
        await message.answer("Usage: /send_global_broadcast <broadcast_id>")
        return
    try:
        draft = await reseller_service.get_global_broadcast_recipients(
            broadcast_id=broadcast_id,
        )
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
    sent = await reseller_service.mark_global_broadcast_sent(
        broadcast_id=draft.broadcast.id,
        delivered_telegram_ids=delivered,
    )
    await message.answer(
        f"Global broadcast sent.\nDelivered: {sent.sent_count}/{sent.target_count}\nID: {sent.id}"
    )


@router.message(Command("global_report"))
async def global_report(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    days = _parse_days(command.args)
    report = await reseller_service.global_report(days=days)
    await message.answer(_format_report(f"Global report - last {days} day(s)", report))


def _parse_days(raw: str | None) -> int:
    if not raw:
        return 1
    try:
        days = int(raw.strip())
    except ValueError:
        return 1
    return max(1, min(days, 365))


def _format_report(title: str, report: dict[str, float | int]) -> str:
    lines = [title]
    for key, value in report.items():
        label = key.replace("_", " ").title()
        if isinstance(value, float):
            lines.append(f"{label}: {value:,.0f}")
        else:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


@router.message(Command("set_forced_join"))
async def set_forced_join(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = (command.args or "").strip().split(maxsplit=1)
    if not args:
        await message.answer("Usage: /set_forced_join <chat_id> [title]")
        return
    chats = [ForcedJoinChat(chat_id=args[0], title=args[1] if len(args) == 2 else None)]
    await reseller_service.set_forced_join_chats(chats=chats)
    await message.answer("Forced join chat saved.")


@router.message(Command("list_forced_join"))
async def list_forced_join(message: Message, reseller_service: ResellerService) -> None:
    chats = await reseller_service.get_forced_join_chats()
    if not chats:
        await message.answer("No forced join chats configured.")
        return
    lines = ["Forced join chats:"]
    for chat in chats:
        lines.append(f"- {chat.chat_id} | {chat.title or '-'}")
    await message.answer("\n".join(lines))
