from __future__ import annotations

import shlex

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.token import TokenValidationError, validate_token

from vpn_bot_platform.common.models import DiscountType, ResellerStatus
from vpn_bot_platform.common.forced_join import ForcedJoinChat
from vpn_bot_platform.common.ui.callbacks import parse_callback
from vpn_bot_platform.common.ui.keyboards import (
    confirm_keyboard,
    inline_keyboard,
    master_main_menu,
    master_section_menu,
    master_seller_bot_actions,
    reseller_card_actions,
    reseller_actions,
)
from vpn_bot_platform.common.ui.messages import section, short_id, status_label, title
from vpn_bot_platform.master_bot.services.resellers import ResellerService

router = Router(name="master_basic")


class ResellerCreateStates(StatesGroup):
    telegram_id = State()
    display_name = State()
    confirm = State()


class ResellerRenameStates(StatesGroup):
    reseller = State()
    display_name = State()
    confirm = State()


class SellerBotCreateStates(StatesGroup):
    reseller = State()
    name = State()
    token = State()
    confirm = State()


class GlobalBroadcastCreateStates(StatesGroup):
    title = State()
    body = State()
    confirm = State()


class PlanCreateStates(StatesGroup):
    reseller = State()
    name = State()
    price = State()
    duration = State()
    data_limit = State()
    confirm = State()


class DiscountCreateStates(StatesGroup):
    code = State()
    discount_type = State()
    amount = State()
    max_uses = State()
    confirm = State()


class PanelTokenCreateStates(StatesGroup):
    name = State()
    base_url = State()
    token = State()
    confirm = State()


class PanelPasswordCreateStates(StatesGroup):
    name = State()
    base_url = State()
    username = State()
    password = State()
    confirm = State()


def _parse_args(raw: str | None) -> list[str]:
    try:
        return shlex.split(raw or "")
    except ValueError:
        return []


@router.message(CommandStart())
async def start(message: Message, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await message.answer(
        _master_dashboard_text(),
        reply_markup=master_main_menu(),
    )


@router.message(Command("admin"))
async def admin_menu(message: Message, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await message.answer(
        _master_dashboard_text(),
        reply_markup=master_main_menu(),
    )


@router.message(Command("cancel"))
@router.message(F.text.in_({"Cancel", "cancel"}))
async def cancel_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "\n".join([title("Canceled"), "Current flow was cleared."]),
        reply_markup=master_main_menu(),
    )


@router.message(F.text.in_({"Resellers", "Seller Bots", "Panels", "Plans", "Reports", "Settings"}))
async def master_reply_menu_alias(
    message: Message,
    reseller_service: ResellerService,
    state: FSMContext,
) -> None:
    await state.clear()
    if message.text == "Resellers":
        await message.answer(await _resellers_text(reseller_service), reply_markup=master_section_menu("resellers"))
    elif message.text == "Seller Bots":
        await message.answer(await _seller_bots_text(reseller_service), reply_markup=master_section_menu("seller_bots"))
    elif message.text == "Panels":
        await message.answer(await _panels_text(reseller_service), reply_markup=master_section_menu("panels"))
    elif message.text == "Plans":
        await message.answer(await _plans_text(reseller_service), reply_markup=master_section_menu("plans"))
    elif message.text == "Reports":
        report = await reseller_service.global_report(days=1)
        await message.answer(_format_report("Global Report - Today", report), reply_markup=master_section_menu("reports"))
    elif message.text == "Settings":
        await message.answer(
            _button_guide_text(
                "Settings",
                "Use these controls for channel and platform configuration.",
                ["/set_forced_join <chat_id> [title]"],
            ),
            reply_markup=master_section_menu("settings"),
        )


@router.callback_query(F.data.startswith("m:"))
async def master_menu_callback(
    callback: CallbackQuery,
    state: FSMContext,
    reseller_service: ResellerService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    action = parse_callback(callback.data or "")
    if action.action == "home":
        await state.clear()
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
    elif action.action in {"reseller_suspended", "reseller_disabled"}:
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller action.", show_alert=True)
            return
        status = action.action.replace("reseller_", "")
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Confirm Reseller Status"),
                    f"Telegram: {action.value}",
                    f"New status: {status_label(status)}",
                    "",
                    "Confirm only if this reseller should lose normal selling access.",
                ]
            ),
            reply_markup=confirm_keyboard(
                scope="m",
                confirm_action="reseller_status_apply",
                cancel_action="reseller_status_cancel",
                value=f"{status}-{action.value}",
            ),
        )
    elif action.action == "reseller_status_cancel":
        await callback.message.edit_text(
            "\n".join([title("Status Canceled"), "No reseller status was changed."]),
            reply_markup=master_section_menu("resellers"),
        )
    elif action.action == "reseller_status_apply":
        if not action.value or "-" not in action.value:
            await callback.answer("Invalid reseller action.", show_alert=True)
            return
        raw_status, raw_telegram_id = action.value.split("-", maxsplit=1)
        if not raw_telegram_id.isdigit():
            await callback.answer("Invalid reseller action.", show_alert=True)
            return
        try:
            status = ResellerStatus(raw_status)
        except ValueError:
            await callback.answer("Invalid reseller status.", show_alert=True)
            return
        try:
            reseller = await reseller_service.set_reseller_status(
                reseller_telegram_id=int(raw_telegram_id),
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
    elif action.action == "reseller_active":
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller action.", show_alert=True)
            return
        try:
            reseller = await reseller_service.set_reseller_status(
                reseller_telegram_id=int(action.value),
                status=ResellerStatus.ACTIVE,
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
        active_seller_bots = [
            seller_bot
            for seller_bot in await reseller_service.list_seller_bots()
            if seller_bot.status != "disabled"
        ]
        for seller_bot in active_seller_bots[:5]:
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
    elif action.action in {
        "seller_detail",
        "seller_start",
        "seller_stop",
        "seller_restart",
        "seller_health",
        "seller_logs",
        "seller_disable",
    }:
        if not action.value:
            await callback.answer("Seller bot is missing.", show_alert=True)
            return
        try:
            if action.action == "seller_detail":
                runtime_status = await reseller_service.seller_health(seller_bot_id=action.value)
                seller_bot = runtime_status.seller_bot
                resellers = await reseller_service.list_resellers()
                reseller = next((item for item in resellers if item.id == seller_bot.reseller_id), None)
                text = "\n".join(
                    [
                        title("Seller Bot Detail"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Reseller: {reseller.display_name if reseller else short_id(seller_bot.reseller_id)}",
                        f"Status: {status_label(seller_bot.status)}",
                        f"Container: {seller_bot.container_name or '-'}",
                        f"Health: {runtime_status.health}",
                        f"Last error: {seller_bot.last_error or '-'}",
                    ]
                )
            elif action.action == "seller_start":
                seller_bot = await reseller_service.start_seller_bot(seller_bot_id=action.value)
                text = "\n".join(
                    [
                        title("Seller Bot Started"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Status: {status_label(seller_bot.status)}",
                    ]
                )
            elif action.action == "seller_restart":
                seller_bot = await reseller_service.restart_seller_bot(seller_bot_id=action.value)
                text = "\n".join(
                    [
                        title("Seller Bot Restarted"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Status: {status_label(seller_bot.status)}",
                        f"Container: {seller_bot.container_name or '-'}",
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
            elif action.action == "seller_disable":
                seller_bot = await reseller_service.disable_seller_bot(seller_bot_id=action.value)
                text = "\n".join(
                    [
                        title("Seller Bot Disabled"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Status: {status_label(seller_bot.status)}",
                        f"Last error: {seller_bot.last_error or '-'}",
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
            await callback.answer("Seller bot not found or token is invalid.", show_alert=True)
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
    elif action.action == "guide_add_panel_token":
        await state.clear()
        await state.set_state(PanelTokenCreateStates.name)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Token Panel"),
                    "Send a short panel name.",
                    "",
                    "Example: Germany Main",
                ]
            ),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "guide_add_panel_password":
        await state.clear()
        await state.set_state(PanelPasswordCreateStates.name)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Login Panel"),
                    "Send a short panel name.",
                    "",
                    "Example: Germany Login",
                ]
            ),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "panel_token_create":
        data = await state.get_data()
        panel_name = str(data.get("panel_token_name") or "").strip()
        base_url = str(data.get("panel_token_base_url") or "").strip()
        token_value = str(data.get("panel_token_value") or "").strip()
        if not panel_name or not base_url or not token_value:
            await callback.answer("Panel draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            panel = await reseller_service.register_marzban_panel(
                name=panel_name,
                base_url=base_url,
                token=token_value,
            )
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Panel Registered"),
                    f"ID: {panel.id}",
                    f"Name: {panel.name}",
                    f"URL: {panel.base_url}",
                    f"Status: {status_label('active' if panel.is_active else 'disabled')}",
                ]
            ),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "panel_token_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Panel Canceled"), "No panel was registered."]),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "panel_password_create":
        data = await state.get_data()
        panel_name = str(data.get("panel_password_name") or "").strip()
        base_url = str(data.get("panel_password_base_url") or "").strip()
        username = str(data.get("panel_password_username") or "").strip()
        password = str(data.get("panel_password_value") or "").strip()
        if not panel_name or not base_url or not username or not password:
            await callback.answer("Panel draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            panel = await reseller_service.register_marzban_panel(
                name=panel_name,
                base_url=base_url,
                username=username,
                password=password,
            )
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Panel Registered"),
                    f"ID: {panel.id}",
                    f"Name: {panel.name}",
                    f"URL: {panel.base_url}",
                    f"Status: {status_label('active' if panel.is_active else 'disabled')}",
                ]
            ),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "panel_password_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Panel Canceled"), "No panel was registered."]),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "plans":
        await callback.message.edit_text(
            await _plans_text(reseller_service),
            reply_markup=master_section_menu("plans"),
        )
    elif action.action == "guide_add_global_plan":
        await state.clear()
        await state.update_data(plan_scope="global")
        await state.set_state(PlanCreateStates.name)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Global Plan"),
                    "Send the plan name.",
                    "",
                    "Example: 30 Days 100GB",
                ]
            ),
            reply_markup=master_section_menu("plans"),
        )
    elif action.action == "guide_add_reseller_plan":
        await state.clear()
        resellers = await reseller_service.list_resellers()
        if not resellers:
            await callback.message.edit_text(
                "\n".join([title("Add Seller Plan"), "Create a reseller first."]),
                reply_markup=master_section_menu("plans"),
            )
            return
        await state.update_data(plan_scope="reseller")
        await state.set_state(PlanCreateStates.reseller)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Seller Plan"),
                    "Select the reseller who should own this custom plan.",
                ]
            ),
            reply_markup=_reseller_select_keyboard(
                resellers[:10],
                action_name="plan_reseller",
                cancel_action="plan_cancel",
            ),
        )
    elif action.action == "plan_reseller":
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller.", show_alert=True)
            return
        await state.update_data(plan_reseller_telegram_id=int(action.value))
        await state.set_state(PlanCreateStates.name)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Seller Plan"),
                    "Send the plan name.",
                    "",
                    "Example: VIP 30 Days",
                ]
            ),
            reply_markup=master_section_menu("plans"),
        )
    elif action.action == "plan_create":
        data = await state.get_data()
        plan_scope = str(data.get("plan_scope") or "").strip()
        plan_name = str(data.get("plan_name") or "").strip()
        price = data.get("plan_price")
        duration_days = data.get("plan_duration_days")
        data_limit_gb = data.get("plan_data_limit_gb")
        if plan_scope not in {"global", "reseller"} or not plan_name or price is None or duration_days is None:
            await callback.answer("Plan draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            if plan_scope == "global":
                plan = await reseller_service.create_global_plan(
                    name=plan_name,
                    price=float(price),
                    duration_days=int(duration_days),
                    data_limit_gb=None if data_limit_gb is None else int(data_limit_gb),
                )
            else:
                reseller_telegram_id = data.get("plan_reseller_telegram_id")
                if not reseller_telegram_id:
                    await callback.answer("Seller plan reseller is missing.", show_alert=True)
                    await state.clear()
                    return
                plan = await reseller_service.create_reseller_plan(
                    reseller_telegram_id=int(reseller_telegram_id),
                    name=plan_name,
                    price=float(price),
                    duration_days=int(duration_days),
                    data_limit_gb=None if data_limit_gb is None else int(data_limit_gb),
                )
        except ValueError:
            await callback.answer("Could not create plan.", show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            _plan_detail_text(plan),
            reply_markup=master_section_menu("plans"),
        )
    elif action.action == "plan_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Plan Canceled"), "No plan was created."]),
            reply_markup=master_section_menu("plans"),
        )
    elif action.action == "discounts":
        await callback.message.edit_text(
            await _discounts_text(reseller_service),
            reply_markup=master_section_menu("discounts"),
        )
    elif action.action == "guide_add_discount":
        await state.clear()
        await state.set_state(DiscountCreateStates.code)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Discount"),
                    "Send the discount code.",
                    "",
                    "Example: SUMMER25",
                ]
            ),
            reply_markup=master_section_menu("discounts"),
        )
    elif action.action == "discount_type":
        if action.value not in {DiscountType.PERCENT.value, DiscountType.FIXED.value}:
            await callback.answer("Invalid discount type.", show_alert=True)
            return
        await state.update_data(discount_type=action.value)
        await state.set_state(DiscountCreateStates.amount)
        unit = "percent value" if action.value == DiscountType.PERCENT.value else "fixed amount"
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Discount"),
                    f"Send the {unit}.",
                    "",
                    "Example: 25",
                ]
            ),
            reply_markup=master_section_menu("discounts"),
        )
    elif action.action == "discount_create":
        data = await state.get_data()
        code = str(data.get("discount_code") or "").strip()
        raw_type = str(data.get("discount_type") or "").strip()
        amount = data.get("discount_amount")
        max_uses = data.get("discount_max_uses")
        if not code or raw_type not in {DiscountType.PERCENT.value, DiscountType.FIXED.value} or amount is None:
            await callback.answer("Discount draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            discount = await reseller_service.create_global_discount(
                code=code,
                discount_type=DiscountType(raw_type),
                amount=float(amount),
                max_uses=None if max_uses is None else int(max_uses),
            )
        except ValueError:
            await callback.answer("Could not create discount.", show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            _discount_detail_text(discount),
            reply_markup=master_section_menu("discounts"),
        )
    elif action.action == "discount_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Discount Canceled"), "No discount was created."]),
            reply_markup=master_section_menu("discounts"),
        )
    elif action.action == "reports":
        report = await reseller_service.global_report(days=1)
        await callback.message.edit_text(
            _format_report("Global Report - Today", report),
            reply_markup=master_section_menu("reports"),
        )
    elif action.action in {"report_1", "report_7", "report_30"}:
        days = int(action.action.replace("report_", ""))
        report = await reseller_service.global_report(days=days)
        label = "Today" if days == 1 else f"Last {days} Days"
        await callback.message.edit_text(
            _format_report(f"Global Report - {label}", report),
            reply_markup=master_section_menu("system"),
        )
    elif action.action == "broadcasts":
        await callback.message.edit_text(
            _button_guide_text(
                "Broadcasts",
                "Create a draft first, then send it after review.",
                ["/global_broadcast <title> | <message>", "/send_global_broadcast <broadcast_id>"],
            ),
            reply_markup=master_section_menu("broadcasts"),
        )
    elif action.action == "guide_global_broadcast":
        await state.clear()
        await state.set_state(GlobalBroadcastCreateStates.title)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Create Broadcast"),
                    "Send the broadcast title.",
                    "",
                    "Example: New plans are available",
                ]
            ),
            reply_markup=master_section_menu("broadcasts"),
        )
    elif action.action == "broadcast_create":
        data = await state.get_data()
        broadcast_title = str(data.get("broadcast_title") or "").strip()
        broadcast_body = str(data.get("broadcast_body") or "").strip()
        if not broadcast_title or not broadcast_body:
            await callback.answer("Broadcast draft is incomplete.", show_alert=True)
            await state.clear()
            return
        draft = await reseller_service.create_global_broadcast(
            admin_telegram_id=callback.from_user.id,
            title=broadcast_title,
            body=broadcast_body,
        )
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Broadcast Draft Created"),
                    f"ID: {draft.broadcast.id}",
                    f"Targets: {len(draft.recipients)}",
                    "",
                    "Use Send Broadcast when you are ready to deliver it.",
                ]
            ),
            reply_markup=master_section_menu("broadcasts"),
        )
    elif action.action == "broadcast_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Broadcast Canceled"), "No broadcast draft was created."]),
            reply_markup=master_section_menu("broadcasts"),
        )
    elif action.action == "settings":
        await callback.message.edit_text(
            _button_guide_text(
                "Settings",
                "Use these controls for channel and platform configuration.",
                ["/set_forced_join <chat_id> [title]"],
            ),
            reply_markup=master_section_menu("settings"),
        )
    elif action.action == "system":
        await callback.message.edit_text(
            _button_guide_text("System", "Choose a report range below.", []),
            reply_markup=master_section_menu("system"),
        )
    elif action.action == "list_forced_join":
        await callback.message.edit_text(
            await _forced_join_text(reseller_service),
            reply_markup=master_section_menu("settings"),
        )
    elif action.action == "guide_add_reseller":
        await state.clear()
        await state.set_state(ResellerCreateStates.telegram_id)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Reseller"),
                    "Send the reseller Telegram numeric ID.",
                    "",
                    "Example: 252486544",
                ]
            ),
            reply_markup=master_section_menu("resellers"),
        )
    elif action.action == "guide_rename_reseller":
        await state.clear()
        resellers = await reseller_service.list_resellers()
        if not resellers:
            await callback.message.edit_text(
                "\n".join([title("Rename Reseller"), "Create a reseller first."]),
                reply_markup=master_section_menu("resellers"),
            )
            return
        await state.set_state(ResellerRenameStates.reseller)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Rename Reseller"),
                    "Select the reseller you want to rename.",
                ]
            ),
            reply_markup=_reseller_select_keyboard(
                resellers[:10],
                action_name="reseller_rename_select",
                cancel_action="reseller_rename_cancel",
            ),
        )
    elif action.action == "reseller_rename_select":
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller.", show_alert=True)
            return
        await state.update_data(rename_reseller_telegram_id=int(action.value))
        await state.set_state(ResellerRenameStates.display_name)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Rename Reseller"),
                    "Send the new display name.",
                    "",
                    "Example: Sina Azad",
                ]
            ),
            reply_markup=master_section_menu("resellers"),
        )
    elif action.action == "reseller_rename":
        data = await state.get_data()
        telegram_id = data.get("rename_reseller_telegram_id")
        display_name = str(data.get("rename_reseller_display_name") or "").strip()
        if not telegram_id or not display_name:
            await callback.answer("Rename draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            reseller = await reseller_service.rename_reseller(
                reseller_telegram_id=int(telegram_id),
                display_name=display_name,
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError:
            await callback.answer("Reseller not found.", show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Reseller Renamed"),
                    f"Name: {reseller.display_name}",
                    f"Telegram: {reseller.telegram_user_id}",
                    f"Status: {status_label(reseller.status)}",
                ]
            ),
            reply_markup=reseller_actions(reseller.telegram_user_id),
        )
    elif action.action == "reseller_rename_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Rename Canceled"), "No reseller was changed."]),
            reply_markup=master_section_menu("resellers"),
        )
    elif action.action == "guide_add_seller_bot":
        await state.clear()
        resellers = await reseller_service.list_resellers()
        if not resellers:
            await callback.message.edit_text(
                "\n".join([title("Add Seller Bot"), "Create a reseller first."]),
                reply_markup=master_section_menu("seller_bots"),
            )
            return
        await state.set_state(SellerBotCreateStates.reseller)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Seller Bot"),
                    "Select the reseller who owns this bot.",
                ]
            ),
            reply_markup=_reseller_select_keyboard(
                resellers[:10],
                action_name="sellerbot_reseller",
                cancel_action="sellerbot_cancel",
            ),
        )
    elif action.action == "sellerbot_reseller":
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller.", show_alert=True)
            return
        await state.update_data(sellerbot_reseller_telegram_id=int(action.value))
        await state.set_state(SellerBotCreateStates.name)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Seller Bot"),
                    "Send the seller bot display name.",
                    "",
                    "Example: Sina Azad",
                ]
            ),
            reply_markup=master_section_menu("seller_bots"),
        )
    elif action.action == "sellerbot_create":
        data = await state.get_data()
        reseller_telegram_id = data.get("sellerbot_reseller_telegram_id")
        bot_name = str(data.get("sellerbot_name") or "").strip()
        bot_token = str(data.get("sellerbot_token") or "").strip()
        if not reseller_telegram_id or not bot_name or not bot_token:
            await callback.answer("Seller bot draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            seller_bot = await reseller_service.register_seller_bot(
                reseller_telegram_id=int(reseller_telegram_id),
                bot_name=bot_name,
                bot_token=bot_token,
            )
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Seller Bot Registered"),
                    f"ID: {seller_bot.id}",
                    f"Name: {seller_bot.name}",
                    f"Status: {status_label(seller_bot.status)}",
                ]
            ),
            reply_markup=master_seller_bot_actions(seller_bot.id),
        )
    elif action.action == "sellerbot_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Seller Bot Canceled"), "No seller bot was registered."]),
            reply_markup=master_section_menu("seller_bots"),
        )
    elif action.action == "reseller_create":
        data = await state.get_data()
        telegram_id = data.get("reseller_telegram_id")
        display_name = str(data.get("reseller_display_name") or "").strip()
        if not telegram_id or not display_name:
            await callback.answer("Reseller draft is incomplete.", show_alert=True)
            await state.clear()
            return
        registered = await reseller_service.register_reseller(
            telegram_id=int(telegram_id),
            display_name=display_name,
        )
        await state.clear()
        status = "already existed" if registered.existed else "created"
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Reseller Created"),
                    f"Status: {status}",
                    f"ID: {registered.reseller.id}",
                    f"Name: {registered.reseller.display_name}",
                    f"Telegram: {registered.reseller.telegram_user_id}",
                ]
            ),
            reply_markup=reseller_actions(registered.reseller.telegram_user_id),
        )
    elif action.action == "reseller_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Reseller Canceled"), "No reseller was created."]),
            reply_markup=master_section_menu("resellers"),
        )
    elif action.action.startswith("guide_"):
        await callback.message.edit_text(
            _master_action_guide_text(action.action),
            reply_markup=_guide_reply_markup(action.action),
        )
    await callback.answer()


@router.message(ResellerCreateStates.telegram_id)
async def reseller_create_telegram_id(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    if not raw_value.isdigit():
        await message.answer(
            "\n".join([title("Add Reseller"), "Send a numeric Telegram ID."]),
            reply_markup=master_section_menu("resellers"),
        )
        return
    await state.update_data(reseller_telegram_id=int(raw_value))
    await state.set_state(ResellerCreateStates.display_name)
    await message.answer(
        "\n".join(
            [
                title("Add Reseller"),
                "Send the reseller display name.",
                "",
                "Example: Sina Azad",
            ]
        ),
        reply_markup=master_section_menu("resellers"),
    )


@router.message(ResellerCreateStates.display_name)
async def reseller_create_display_name(message: Message, state: FSMContext) -> None:
    display_name = (message.text or "").strip()
    if not display_name or display_name.startswith("/"):
        await message.answer(
            "\n".join([title("Add Reseller"), "Send a display name, not a command."]),
            reply_markup=master_section_menu("resellers"),
        )
        return
    await state.update_data(reseller_display_name=display_name[:128])
    await state.set_state(ResellerCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Reseller"),
                f"Telegram: {data.get('reseller_telegram_id')}",
                f"Name: {data.get('reseller_display_name')}",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="reseller_create",
            cancel_action="reseller_cancel",
        ),
    )


@router.message(ResellerCreateStates.confirm)
async def reseller_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Reseller"), "Use Confirm or Cancel below the preview."])
    )


@router.message(ResellerRenameStates.reseller)
async def reseller_rename_waiting_for_reseller(message: Message) -> None:
    await message.answer(
        "\n".join([title("Rename Reseller"), "Select a reseller using the buttons."])
    )


@router.message(ResellerRenameStates.display_name)
async def reseller_rename_display_name(message: Message, state: FSMContext) -> None:
    display_name = (message.text or "").strip()
    if not display_name or display_name.startswith("/"):
        await message.answer(
            "\n".join([title("Rename Reseller"), "Send a display name, not a command."]),
            reply_markup=master_section_menu("resellers"),
        )
        return
    await state.update_data(rename_reseller_display_name=display_name[:128])
    await state.set_state(ResellerRenameStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Rename"),
                f"Telegram: {data.get('rename_reseller_telegram_id')}",
                f"New name: {data.get('rename_reseller_display_name')}",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="reseller_rename",
            cancel_action="reseller_rename_cancel",
        ),
    )


@router.message(ResellerRenameStates.confirm)
async def reseller_rename_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Rename"), "Use Confirm or Cancel below the preview."])
    )


@router.message(SellerBotCreateStates.reseller)
async def sellerbot_create_waiting_for_reseller(message: Message) -> None:
    await message.answer(
        "\n".join([title("Add Seller Bot"), "Select a reseller using the buttons."])
    )


@router.message(SellerBotCreateStates.name)
async def sellerbot_create_name(message: Message, state: FSMContext) -> None:
    bot_name = (message.text or "").strip()
    if not bot_name or bot_name.startswith("/"):
        await message.answer(
            "\n".join([title("Add Seller Bot"), "Send a display name, not a command."]),
            reply_markup=master_section_menu("seller_bots"),
        )
        return
    await state.update_data(sellerbot_name=bot_name[:128])
    await state.set_state(SellerBotCreateStates.token)
    await message.answer(
        "\n".join(
            [
                title("Add Seller Bot"),
                "Send the Telegram bot token from BotFather.",
                "",
                "The token will be encrypted and will not be shown back.",
            ]
        ),
        reply_markup=master_section_menu("seller_bots"),
    )


@router.message(SellerBotCreateStates.token)
async def sellerbot_create_token(message: Message, state: FSMContext) -> None:
    bot_token = (message.text or "").strip()
    try:
        validate_token(bot_token)
    except TokenValidationError as exc:
        await message.answer(
            "\n".join([title("Add Seller Bot"), f"Invalid token: {exc}", "Send a valid BotFather token."]),
            reply_markup=master_section_menu("seller_bots"),
        )
        return
    await state.update_data(sellerbot_token=bot_token)
    await state.set_state(SellerBotCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Seller Bot"),
                f"Reseller Telegram: {data.get('sellerbot_reseller_telegram_id')}",
                f"Bot name: {data.get('sellerbot_name')}",
                "Token: valid and hidden",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="sellerbot_create",
            cancel_action="sellerbot_cancel",
        ),
    )


@router.message(SellerBotCreateStates.confirm)
async def sellerbot_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Seller Bot"), "Use Confirm or Cancel below the preview."])
    )


@router.message(GlobalBroadcastCreateStates.title)
async def broadcast_create_title(message: Message, state: FSMContext) -> None:
    broadcast_title = (message.text or "").strip()
    if not broadcast_title or broadcast_title.startswith("/"):
        await message.answer(
            "\n".join([title("Create Broadcast"), "Send a title, not a command."]),
            reply_markup=master_section_menu("broadcasts"),
        )
        return
    await state.update_data(broadcast_title=broadcast_title[:160])
    await state.set_state(GlobalBroadcastCreateStates.body)
    await message.answer(
        "\n".join(
            [
                title("Create Broadcast"),
                "Send the message body.",
                "",
                "This will be previewed before any draft is created.",
            ]
        ),
        reply_markup=master_section_menu("broadcasts"),
    )


@router.message(GlobalBroadcastCreateStates.body)
async def broadcast_create_body(message: Message, state: FSMContext) -> None:
    broadcast_body = (message.text or "").strip()
    if not broadcast_body or broadcast_body.startswith("/"):
        await message.answer(
            "\n".join([title("Create Broadcast"), "Send a message body, not a command."]),
            reply_markup=master_section_menu("broadcasts"),
        )
        return
    await state.update_data(broadcast_body=broadcast_body[:3500])
    await state.set_state(GlobalBroadcastCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Broadcast Draft"),
                f"Title: {data.get('broadcast_title')}",
                "",
                str(data.get("broadcast_body")),
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="broadcast_create",
            cancel_action="broadcast_cancel",
        ),
    )


@router.message(GlobalBroadcastCreateStates.confirm)
async def broadcast_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Broadcast Draft"), "Use Confirm or Cancel below the preview."])
    )


@router.message(PlanCreateStates.reseller)
async def plan_create_waiting_for_reseller(message: Message) -> None:
    await message.answer(
        "\n".join([title("Add Seller Plan"), "Select a reseller using the buttons."])
    )


@router.message(PlanCreateStates.name)
async def plan_create_name(message: Message, state: FSMContext) -> None:
    plan_name = (message.text or "").strip()
    if not plan_name or plan_name.startswith("/"):
        await message.answer(
            "\n".join([title("Add Plan"), "Send a plan name, not a command."]),
            reply_markup=master_section_menu("plans"),
        )
        return
    await state.update_data(plan_name=plan_name[:128])
    await state.set_state(PlanCreateStates.price)
    await message.answer(
        "\n".join(
            [
                title("Add Plan"),
                "Send the price.",
                "",
                "Example: 250000",
            ]
        ),
        reply_markup=master_section_menu("plans"),
    )


@router.message(PlanCreateStates.price)
async def plan_create_price(message: Message, state: FSMContext) -> None:
    price = _parse_positive_float(message.text)
    if price is None:
        await message.answer(
            "\n".join([title("Add Plan"), "Send a valid price greater than zero. Example: 250000"]),
            reply_markup=master_section_menu("plans"),
        )
        return
    await state.update_data(plan_price=price)
    await state.set_state(PlanCreateStates.duration)
    await message.answer(
        "\n".join(
            [
                title("Add Plan"),
                "Send the duration in days.",
                "",
                "Example: 30",
            ]
        ),
        reply_markup=master_section_menu("plans"),
    )


@router.message(PlanCreateStates.duration)
async def plan_create_duration(message: Message, state: FSMContext) -> None:
    duration_days = _parse_positive_int(message.text)
    if duration_days is None:
        await message.answer(
            "\n".join([title("Add Plan"), "Send a valid duration in days. Example: 30"]),
            reply_markup=master_section_menu("plans"),
        )
        return
    await state.update_data(plan_duration_days=duration_days)
    await state.set_state(PlanCreateStates.data_limit)
    await message.answer(
        "\n".join(
            [
                title("Add Plan"),
                "Send the data limit in GB, or send unlimited.",
                "",
                "Example: 100",
            ]
        ),
        reply_markup=master_section_menu("plans"),
    )


@router.message(PlanCreateStates.data_limit)
async def plan_create_data_limit(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip().lower()
    if raw_value == "unlimited":
        data_limit_gb = None
    else:
        data_limit_gb = _parse_positive_int(raw_value)
        if data_limit_gb is None:
            await message.answer(
                "\n".join([title("Add Plan"), "Send a valid GB value or unlimited. Example: 100"]),
                reply_markup=master_section_menu("plans"),
            )
            return
    await state.update_data(plan_data_limit_gb=data_limit_gb)
    await state.set_state(PlanCreateStates.confirm)
    data = await state.get_data()
    traffic = "Unlimited" if data_limit_gb is None else f"{data_limit_gb} GB"
    scope = "Global" if data.get("plan_scope") == "global" else "Seller"
    rows = [
        title("Confirm Plan"),
        f"Scope: {scope}",
        f"Name: {data.get('plan_name')}",
        f"Price: {float(data.get('plan_price')):,.0f}",
        f"Duration: {data.get('plan_duration_days')} days",
        f"Traffic: {traffic}",
    ]
    if data.get("plan_reseller_telegram_id"):
        rows.insert(2, f"Reseller Telegram: {data.get('plan_reseller_telegram_id')}")
    await message.answer(
        "\n".join(rows),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="plan_create",
            cancel_action="plan_cancel",
        ),
    )


@router.message(PlanCreateStates.confirm)
async def plan_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Plan"), "Use Confirm or Cancel below the preview."])
    )


@router.message(DiscountCreateStates.code)
async def discount_create_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip().upper()
    if not code or code.startswith("/") or len(code) > 64:
        await message.answer(
            "\n".join([title("Add Discount"), "Send a code up to 64 characters, not a command."]),
            reply_markup=master_section_menu("discounts"),
        )
        return
    await state.update_data(discount_code=code)
    await state.set_state(DiscountCreateStates.discount_type)
    await message.answer(
        "\n".join([title("Add Discount"), "Choose the discount type."]),
        reply_markup=inline_keyboard(
            [
                [
                    ("Percent", "m:discount_type:percent"),
                    ("Fixed", "m:discount_type:fixed"),
                ],
                [("Cancel", "m:discount_cancel"), ("Home", "m:home")],
            ]
        ),
    )


@router.message(DiscountCreateStates.discount_type)
async def discount_create_waiting_for_type(message: Message) -> None:
    await message.answer(
        "\n".join([title("Add Discount"), "Choose Percent or Fixed using the buttons."])
    )


@router.message(DiscountCreateStates.amount)
async def discount_create_amount(message: Message, state: FSMContext) -> None:
    amount = _parse_positive_float(message.text)
    data = await state.get_data()
    discount_type = str(data.get("discount_type") or "")
    if amount is None or (discount_type == DiscountType.PERCENT.value and amount > 100):
        await message.answer(
            "\n".join([title("Add Discount"), "Send a valid amount. Percent discounts must be 100 or less."]),
            reply_markup=master_section_menu("discounts"),
        )
        return
    await state.update_data(discount_amount=amount)
    await state.set_state(DiscountCreateStates.max_uses)
    await message.answer(
        "\n".join(
            [
                title("Add Discount"),
                "Send max uses, or send unlimited.",
                "",
                "Example: 50",
            ]
        ),
        reply_markup=master_section_menu("discounts"),
    )


@router.message(DiscountCreateStates.max_uses)
async def discount_create_max_uses(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip().lower()
    if raw_value == "unlimited":
        max_uses = None
    else:
        max_uses = _parse_positive_int(raw_value)
        if max_uses is None:
            await message.answer(
                "\n".join([title("Add Discount"), "Send a valid max-use number or unlimited."]),
                reply_markup=master_section_menu("discounts"),
            )
            return
    await state.update_data(discount_max_uses=max_uses)
    await state.set_state(DiscountCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Discount"),
                f"Code: {data.get('discount_code')}",
                f"Type: {data.get('discount_type')}",
                f"Amount: {float(data.get('discount_amount')):g}",
                f"Max uses: {max_uses if max_uses is not None else 'Unlimited'}",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="discount_create",
            cancel_action="discount_cancel",
        ),
    )


@router.message(DiscountCreateStates.confirm)
async def discount_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Discount"), "Use Confirm or Cancel below the preview."])
    )


@router.message(PanelTokenCreateStates.name)
async def panel_token_create_name(message: Message, state: FSMContext) -> None:
    panel_name = (message.text or "").strip()
    if not panel_name or panel_name.startswith("/"):
        await message.answer(
            "\n".join([title("Add Token Panel"), "Send a panel name, not a command."]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_token_name=panel_name[:128])
    await state.set_state(PanelTokenCreateStates.base_url)
    await message.answer(
        "\n".join(
            [
                title("Add Token Panel"),
                "Send the Marzban base URL.",
                "",
                "Example: https://panel.example.com",
            ]
        ),
        reply_markup=master_section_menu("panels"),
    )


@router.message(PanelTokenCreateStates.base_url)
async def panel_token_create_base_url(message: Message, state: FSMContext) -> None:
    base_url = (message.text or "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        await message.answer(
            "\n".join([title("Add Token Panel"), "Send a valid URL starting with http:// or https://."]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_token_base_url=base_url)
    await state.set_state(PanelTokenCreateStates.token)
    await message.answer(
        "\n".join(
            [
                title("Add Token Panel"),
                "Send the Marzban admin token.",
                "",
                "The token will be encrypted and hidden in the preview.",
            ]
        ),
        reply_markup=master_section_menu("panels"),
    )


@router.message(PanelTokenCreateStates.token)
async def panel_token_create_token(message: Message, state: FSMContext) -> None:
    token_value = (message.text or "").strip()
    if not token_value or token_value.startswith("/"):
        await message.answer(
            "\n".join([title("Add Token Panel"), "Send the panel token, not a command."]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_token_value=token_value)
    await state.set_state(PanelTokenCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Token Panel"),
                f"Name: {data.get('panel_token_name')}",
                f"URL: {data.get('panel_token_base_url')}",
                "Token: hidden",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="panel_token_create",
            cancel_action="panel_token_cancel",
        ),
    )


@router.message(PanelTokenCreateStates.confirm)
async def panel_token_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Token Panel"), "Use Confirm or Cancel below the preview."])
    )


@router.message(PanelPasswordCreateStates.name)
async def panel_password_create_name(message: Message, state: FSMContext) -> None:
    panel_name = (message.text or "").strip()
    if not panel_name or panel_name.startswith("/"):
        await message.answer(
            "\n".join([title("Add Login Panel"), "Send a panel name, not a command."]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_password_name=panel_name[:128])
    await state.set_state(PanelPasswordCreateStates.base_url)
    await message.answer(
        "\n".join(
            [
                title("Add Login Panel"),
                "Send the Marzban base URL.",
                "",
                "Example: https://panel.example.com",
            ]
        ),
        reply_markup=master_section_menu("panels"),
    )


@router.message(PanelPasswordCreateStates.base_url)
async def panel_password_create_base_url(message: Message, state: FSMContext) -> None:
    base_url = (message.text or "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        await message.answer(
            "\n".join([title("Add Login Panel"), "Send a valid URL starting with http:// or https://."]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_password_base_url=base_url)
    await state.set_state(PanelPasswordCreateStates.username)
    await message.answer(
        "\n".join([title("Add Login Panel"), "Send the Marzban admin username."]),
        reply_markup=master_section_menu("panels"),
    )


@router.message(PanelPasswordCreateStates.username)
async def panel_password_create_username(message: Message, state: FSMContext) -> None:
    username = (message.text or "").strip()
    if not username or username.startswith("/"):
        await message.answer(
            "\n".join([title("Add Login Panel"), "Send a username, not a command."]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_password_username=username[:128])
    await state.set_state(PanelPasswordCreateStates.password)
    await message.answer(
        "\n".join(
            [
                title("Add Login Panel"),
                "Send the Marzban admin password.",
                "",
                "The password will be encrypted and hidden in the preview.",
            ]
        ),
        reply_markup=master_section_menu("panels"),
    )


@router.message(PanelPasswordCreateStates.password)
async def panel_password_create_password(message: Message, state: FSMContext) -> None:
    password = (message.text or "").strip()
    if not password or password.startswith("/"):
        await message.answer(
            "\n".join([title("Add Login Panel"), "Send the panel password, not a command."]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_password_value=password)
    await state.set_state(PanelPasswordCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Login Panel"),
                f"Name: {data.get('panel_password_name')}",
                f"URL: {data.get('panel_password_base_url')}",
                f"Username: {data.get('panel_password_username')}",
                "Password: hidden",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="panel_password_create",
            cancel_action="panel_password_cancel",
        ),
    )


@router.message(PanelPasswordCreateStates.confirm)
async def panel_password_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Login Panel"), "Use Confirm or Cancel below the preview."])
    )


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
        if str(exc) == "seller_token_invalid":
            await message.answer("Seller token is invalid. Disable this seller bot and register a fresh token.")
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


@router.message(Command("disable_seller"))
async def disable_seller(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    seller_bot_id = (command.args or "").strip()
    if not seller_bot_id:
        await message.answer("Usage: /disable_seller <seller_bot_id>")
        return

    try:
        seller_bot = await reseller_service.disable_seller_bot(seller_bot_id=seller_bot_id)
    except ValueError as exc:
        if str(exc) == "seller_bot_not_found":
            await message.answer("Seller bot not found.")
            return
        raise

    await message.answer(
        "\n".join(
            [
                "Seller bot disabled.",
                f"ID: {seller_bot.id}",
                f"Status: {seller_bot.status}",
                f"Last error: {seller_bot.last_error or '-'}",
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
            "Use the buttons below to add, rename, activate, suspend, or disable resellers.",
        ]
    )
    return "\n".join([title("Resellers"), section("Latest resellers", rows)])


def _reseller_select_keyboard(resellers, *, action_name: str, cancel_action: str):
    rows = [
        [(reseller.display_name, f"m:{action_name}:{reseller.telegram_user_id}")]
        for reseller in resellers
    ]
    rows.append(
        [
            ("Cancel", f"m:{cancel_action}"),
            ("Home", "m:home"),
        ]
    )
    return inline_keyboard(rows)


async def _panels_text(reseller_service: ResellerService) -> str:
    panels = await reseller_service.list_marzban_panels()
    rows = [
        f"- {panel.name} | {status_label('active' if panel.is_active else 'disabled')} | id={short_id(panel.id)}"
        for panel in panels[:20]
    ]
    rows.extend(["", "Use the buttons below to add or assign panels."])
    return "\n".join([title("Panels"), section("Registered panels", rows)])


async def _seller_bots_text(reseller_service: ResellerService) -> str:
    seller_bots = [
        seller_bot
        for seller_bot in await reseller_service.list_seller_bots()
        if seller_bot.status != "disabled"
    ]
    rows = [
        (
            f"- {seller_bot.name} | {status_label(seller_bot.status)} | "
            f"id={short_id(seller_bot.id)} | container={seller_bot.container_name or '-'}"
        )
        for seller_bot in seller_bots[:20]
    ]
    rows.extend(["", "Use the buttons below to add or manage seller bots."])
    return "\n".join([title("Seller Bots"), section("Registered bots", rows)])


async def _plans_text(reseller_service: ResellerService) -> str:
    plans = await reseller_service.list_plans()
    rows = []
    for plan in plans[:20]:
        scope = "global" if plan.reseller_id is None else f"reseller={short_id(plan.reseller_id)}"
        traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
        rows.append(f"- {plan.name} | {scope} | {plan.price:,.0f} | {plan.duration_days}d | {traffic}")
    rows.extend(["", "Use the buttons below to add global or seller-specific plans."])
    return "\n".join([title("Plans"), section("Active catalog", rows)])


def _plan_detail_text(plan) -> str:
    scope = "Global" if plan.reseller_id is None else f"Seller {short_id(plan.reseller_id)}"
    traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
    return "\n".join(
        [
            title("Plan Created"),
            f"ID: {plan.id}",
            f"Scope: {scope}",
            f"Name: {plan.name}",
            f"Price: {plan.price:,.0f}",
            f"Duration: {plan.duration_days} days",
            f"Traffic: {traffic}",
            f"Status: {status_label('active' if plan.is_active else 'disabled')}",
        ]
    )


async def _discounts_text(reseller_service: ResellerService) -> str:
    discounts = await reseller_service.list_discounts()
    rows = [
        (
            f"- {discount.code} | {discount.discount_type} {discount.amount} | "
            f"used={discount.used_count}/{discount.max_uses or 'unlimited'}"
        )
        for discount in discounts[:20]
    ]
    rows.extend(["", "Use the buttons below to create new discount codes."])
    return "\n".join([title("Discounts"), section("Discount codes", rows)])


def _discount_detail_text(discount) -> str:
    scope = "Global" if discount.reseller_id is None else f"Seller {short_id(discount.reseller_id)}"
    max_uses = "Unlimited" if discount.max_uses is None else str(discount.max_uses)
    return "\n".join(
        [
            title("Discount Created"),
            f"ID: {discount.id}",
            f"Scope: {scope}",
            f"Code: {discount.code}",
            f"Type: {discount.discount_type}",
            f"Amount: {discount.amount:g}",
            f"Uses: {discount.used_count}/{max_uses}",
            f"Status: {status_label('active' if discount.is_active else 'disabled')}",
        ]
    )


def _button_guide_text(name: str, description: str, examples: list[str]) -> str:
    rows = [title(name), description]
    if examples:
        rows.extend(["", "When text is required, send one message in this format:", *[f"- {item}" for item in examples]])
    return "\n".join(rows)


def _master_action_guide_text(action: str) -> str:
    guides = {
        "guide_add_reseller": (
            "Add Reseller",
            "Create an admin/reseller account.",
            ["/add_reseller <telegram_id> <display_name>"],
        ),
        "guide_rename_reseller": (
            "Rename Reseller",
            "Change a reseller display name.",
            ["/rename_reseller <telegram_id> <display_name>"],
        ),
        "guide_add_seller_bot": (
            "Add Seller Bot",
            "Register a reseller bot token. Put bot names with spaces inside quotes.",
            ['/add_seller_bot <reseller_telegram_id> "Bot Name" <bot_token>'],
        ),
        "guide_botfather": (
            "BotFather",
            "Create a Telegram bot with BotFather, copy the token, then return here and add it.",
            ['/add_seller_bot <reseller_telegram_id> "Bot Name" <bot_token>'],
        ),
        "guide_add_panel_token": (
            "Add Panel With Token",
            "Connect a Marzban panel using an existing admin token.",
            ["/add_panel_token <name> <base_url> <token>"],
        ),
        "guide_add_panel_password": (
            "Add Panel With Login",
            "Connect a Marzban panel using username and password.",
            ["/add_panel_password <name> <base_url> <username> <password>"],
        ),
        "guide_assign_panel": (
            "Assign Panel",
            "Attach a panel to a reseller.",
            ["/assign_panel <reseller_telegram_id> <panel_id> [marzban_admin_username]"],
        ),
        "guide_add_global_plan": (
            "Add Global Plan",
            "Create a base plan visible to sellers.",
            ["/add_global_plan <name> <price> <duration_days> <data_limit_gb|unlimited>"],
        ),
        "guide_add_reseller_plan": (
            "Add Seller Plan",
            "Create a custom plan for one reseller.",
            ["/add_reseller_plan <reseller_telegram_id> <name> <price> <duration_days> <data_limit_gb|unlimited>"],
        ),
        "guide_add_discount": (
            "Add Discount",
            "Create a percent or fixed discount code.",
            ["/add_discount <code> <percent|fixed> <amount> [max_uses]"],
        ),
        "guide_global_broadcast": (
            "Create Broadcast",
            "Draft a message for all known users.",
            ["/global_broadcast <title> | <message>"],
        ),
        "guide_send_global_broadcast": (
            "Send Broadcast",
            "Send an already drafted broadcast.",
            ["/send_global_broadcast <broadcast_id>"],
        ),
        "guide_set_forced_join": (
            "Forced Join",
            "Require users to join a channel or group before using seller bots.",
            ["/set_forced_join <chat_id> [title]"],
        ),
    }
    heading, description, examples = guides.get(
        action,
        ("Action", "Choose a button from the menu.", []),
    )
    return _button_guide_text(heading, description, examples)


def _guide_reply_markup(action: str):
    if "reseller" in action and "plan" not in action:
        return master_section_menu("resellers")
    if "seller_bot" in action or "botfather" in action:
        return master_section_menu("seller_bots")
    if "panel" in action:
        return master_section_menu("panels")
    if "plan" in action:
        return master_section_menu("plans")
    if "discount" in action:
        return master_section_menu("discounts")
    if "broadcast" in action:
        return master_section_menu("broadcasts")
    if "forced_join" in action:
        return master_section_menu("settings")
    return master_main_menu()


async def _forced_join_text(reseller_service: ResellerService) -> str:
    chats = await reseller_service.get_forced_join_chats()
    if not chats:
        return "\n".join([title("Forced Join"), "No forced join chats configured."])
    rows = [f"- {chat.chat_id} | {chat.title or '-'}" for chat in chats]
    return "\n".join([title("Forced Join"), section("Required chats", rows)])


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


def _parse_positive_float(raw: str | None) -> float | None:
    try:
        value = float((raw or "").strip().replace(",", ""))
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _parse_positive_int(raw: str | None) -> int | None:
    try:
        value = int((raw or "").strip().replace(",", ""))
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


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
