from __future__ import annotations

import shlex

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from vpn_bot_platform.common.models import DiscountType, ResellerStatus
from vpn_bot_platform.common.forced_join import ForcedJoinChat
from vpn_bot_platform.common.ui.callbacks import parse_callback
from vpn_bot_platform.common.ui.keyboards import (
    master_main_menu,
    master_section_menu,
    master_seller_bot_actions,
    reseller_card_actions,
    reseller_actions,
)
from vpn_bot_platform.common.ui.messages import section, short_id, status_label, title
from vpn_bot_platform.master_bot.services.resellers import ResellerService

router = Router(name="master_basic")


def _parse_args(raw: str | None) -> list[str]:
    try:
        return shlex.split(raw or "")
    except ValueError:
        return []


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        _master_dashboard_text(),
        reply_markup=master_main_menu(),
    )


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    await message.answer(
        _master_dashboard_text(),
        reply_markup=master_main_menu(),
    )


@router.callback_query(F.data.startswith("m:"))
async def master_menu_callback(
    callback: CallbackQuery,
    reseller_service: ResellerService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    action = parse_callback(callback.data or "")
    if action.action == "home":
        await callback.message.edit_text(_master_dashboard_text(), reply_markup=master_main_menu())
    elif action.action == "resellers":
        await callback.message.edit_text(
            await _resellers_text(reseller_service),
            reply_markup=master_section_menu("resellers"),
        )
        for reseller in (await reseller_service.list_resellers())[:5]:
            await callback.message.answer(
                "\n".join(
                    [
                        title("Reseller Action"),
                        f"Name: {reseller.display_name}",
                        f"Telegram: {reseller.telegram_user_id}",
                        f"Status: {status_label(reseller.status)}",
                    ]
                ),
                reply_markup=reseller_card_actions(reseller.telegram_user_id),
            )
    elif action.action in {"reseller_active", "reseller_suspended", "reseller_disabled"}:
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller action.", show_alert=True)
            return
        status = ResellerStatus(action.action.replace("reseller_", ""))
        try:
            reseller = await reseller_service.set_reseller_status(
                reseller_telegram_id=int(action.value),
                status=status,
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError:
            await callback.answer("Reseller not found.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Reseller Updated"),
                    f"Name: {reseller.display_name}",
                    f"Telegram: {reseller.telegram_user_id}",
                    f"Status: {status_label(reseller.status)}",
                ]
            ),
            reply_markup=reseller_actions(reseller.telegram_user_id),
        )
    elif action.action == "seller_bots":
        await callback.message.edit_text(
            await _seller_bots_text(reseller_service),
            reply_markup=master_section_menu("seller_bots"),
        )
        for seller_bot in (await reseller_service.list_seller_bots())[:5]:
            await callback.message.answer(
                "\n".join(
                    [
                        title("Seller Bot Action"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Status: {status_label(seller_bot.status)}",
                        f"Container: {seller_bot.container_name or '-'}",
                    ]
                ),
                reply_markup=master_seller_bot_actions(seller_bot.id),
            )
    elif action.action in {"seller_start", "seller_stop", "seller_health", "seller_logs"}:
        if not action.value:
            await callback.answer("Seller bot is missing.", show_alert=True)
            return
        try:
            if action.action == "seller_start":
                seller_bot = await reseller_service.start_seller_bot(seller_bot_id=action.value)
                text = "\n".join(
                    [
                        title("Seller Bot Started"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Status: {status_label(seller_bot.status)}",
                    ]
                )
            elif action.action == "seller_stop":
                seller_bot = await reseller_service.stop_seller_bot(seller_bot_id=action.value)
                text = "\n".join(
                    [
                        title("Seller Bot Stopped"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Status: {status_label(seller_bot.status)}",
                    ]
                )
            elif action.action == "seller_health":
                runtime_status = await reseller_service.seller_health(seller_bot_id=action.value)
                seller_bot = runtime_status.seller_bot
                text = "\n".join(
                    [
                        title("Seller Bot Health"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Status: {status_label(seller_bot.status)}",
                        f"Health: {runtime_status.health}",
                        f"Last error: {seller_bot.last_error or '-'}",
                    ]
                )
            else:
                runtime_status = await reseller_service.seller_logs(seller_bot_id=action.value)
                seller_bot = runtime_status.seller_bot
                logs = (runtime_status.logs or "").strip() or "(no logs)"
                text = "\n".join(
                    [
                        title("Seller Bot Logs"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        "",
                        _telegram_code_block(logs[-2500:]),
                    ]
                )
        except ValueError:
            await callback.answer("Seller bot not found.", show_alert=True)
            return
        except RuntimeError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await callback.message.edit_text(text, reply_markup=master_seller_bot_actions(action.value))
    elif action.action == "panels":
        await callback.message.edit_text(
            await _panels_text(reseller_service),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "plans":
        await callback.message.edit_text(
            await _plans_text(reseller_service),
            reply_markup=master_section_menu("plans"),
        )
    elif action.action == "discounts":
        await callback.message.edit_text(
            await _discounts_text(reseller_service),
            reply_markup=master_section_menu("discounts"),
        )
    elif action.action == "reports":
        report = await reseller_service.global_report(days=1)
        await callback.message.edit_text(
            _format_report("Global Report - Today", report),
            reply_markup=master_section_menu("reports"),
        )
    elif action.action == "broadcasts":
        await callback.message.edit_text(
            _shortcut_text("Broadcasts", ["/global_broadcast", "/send_global_broadcast"]),
            reply_markup=master_section_menu("broadcasts"),
        )
    elif action.action == "settings":
        await callback.message.edit_text(
            _shortcut_text("Settings", ["/set_forced_join", "/list_forced_join"]),
            reply_markup=master_section_menu("settings"),
        )
    elif action.action == "system":
        await callback.message.edit_text(
            _shortcut_text("System", ["/global_report", "/seller_health", "/seller_logs"]),
            reply_markup=master_section_menu("system"),
        )
    await callback.answer()


@router.message(Command("add_reseller"))
async def add_reseller(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = _parse_args(command.args)
    if len(args) < 2 or not args[0].isdigit():
        await message.answer("Usage: /add_reseller <telegram_id> <display_name>")
        return
    display_name = " ".join(args[1:]).strip()

    registered = await reseller_service.register_reseller(
        telegram_id=int(args[0]),
        display_name=display_name,
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
    args = _parse_args(command.args)
    if len(args) < 2 or not args[0].isdigit():
        await message.answer("Usage: /rename_reseller <telegram_id> <display_name>")
        return
    display_name = " ".join(args[1:]).strip()
    try:
        reseller = await reseller_service.rename_reseller(
            reseller_telegram_id=int(args[0]),
            display_name=display_name,
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
    args = _parse_args(command.args)
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
    args = _parse_args(command.args)
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
    args = _parse_args(command.args)
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
    args = _parse_args(command.args)
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
    args = _parse_args(command.args)
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


def _master_dashboard_text() -> str:
    return "\n".join(
        [
            title("Master Dashboard"),
            "Use the buttons below for daily operations.",
            "",
            section(
                "Quick commands",
                [
                    "- /add_reseller <telegram_id> <display_name>",
                    "- /add_seller_bot <reseller_telegram_id> <bot_name> <bot_token>",
                    "- /add_panel_token <name> <base_url> <token>",
                    "- /global_report [days]",
                ],
            ),
        ]
    )


async def _resellers_text(reseller_service: ResellerService) -> str:
    resellers = await reseller_service.list_resellers()
    rows = [
        (
            f"- {reseller.display_name} | tg={reseller.telegram_user_id} | "
            f"{status_label(reseller.status)} | id={short_id(reseller.id)}"
        )
        for reseller in resellers[:20]
    ]
    rows.extend(
        [
            "",
            "Shortcuts:",
            "/add_reseller <telegram_id> <display_name>",
            "/rename_reseller <telegram_id> <display_name>",
            "/set_reseller_status <telegram_id> <active|suspended|disabled>",
        ]
    )
    return "\n".join([title("Resellers"), section("Latest resellers", rows)])


async def _panels_text(reseller_service: ResellerService) -> str:
    panels = await reseller_service.list_marzban_panels()
    rows = [
        f"- {panel.name} | {status_label('active' if panel.is_active else 'disabled')} | id={short_id(panel.id)}"
        for panel in panels[:20]
    ]
    rows.extend(["", "Shortcuts:", "/add_panel_token", "/add_panel_password", "/assign_panel"])
    return "\n".join([title("Panels"), section("Registered panels", rows)])


async def _seller_bots_text(reseller_service: ResellerService) -> str:
    seller_bots = await reseller_service.list_seller_bots()
    rows = [
        (
            f"- {seller_bot.name} | {status_label(seller_bot.status)} | "
            f"id={short_id(seller_bot.id)} | container={seller_bot.container_name or '-'}"
        )
        for seller_bot in seller_bots[:20]
    ]
    rows.extend(["", "Shortcuts:", "/add_seller_bot", "/start_seller", "/stop_seller"])
    return "\n".join([title("Seller Bots"), section("Registered bots", rows)])


async def _plans_text(reseller_service: ResellerService) -> str:
    plans = await reseller_service.list_plans()
    rows = []
    for plan in plans[:20]:
        scope = "global" if plan.reseller_id is None else f"reseller={short_id(plan.reseller_id)}"
        traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
        rows.append(f"- {plan.name} | {scope} | {plan.price:,.0f} | {plan.duration_days}d | {traffic}")
    rows.extend(["", "Shortcuts:", "/add_global_plan", "/add_reseller_plan", "/list_plans"])
    return "\n".join([title("Plans"), section("Active catalog", rows)])


async def _discounts_text(reseller_service: ResellerService) -> str:
    discounts = await reseller_service.list_discounts()
    rows = [
        (
            f"- {discount.code} | {discount.discount_type} {discount.amount} | "
            f"used={discount.used_count}/{discount.max_uses or 'unlimited'}"
        )
        for discount in discounts[:20]
    ]
    rows.extend(["", "Shortcuts:", "/add_discount", "/list_discounts"])
    return "\n".join([title("Discounts"), section("Discount codes", rows)])


def _shortcut_text(name: str, commands: list[str]) -> str:
    return "\n".join(
        [
            title(name),
            "Button flow for this area is staged. Use these shortcuts now:",
            "",
            *[f"- {command}" for command in commands],
        ]
    )


@router.message(Command("add_global_plan"))
async def add_global_plan(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = _parse_args(command.args)
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
    args = _parse_args(command.args)
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
    args = _parse_args(command.args)
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
    args = _parse_args(command.args)
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
