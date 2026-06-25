from __future__ import annotations

import re
import shlex

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.token import TokenValidationError, validate_token

from vpn_bot_platform.common.models import DiscountType, PlanPurpose, ResellerStatus, SellerBotUiProfile
from vpn_bot_platform.common.forced_join import ForcedJoinChat
from vpn_bot_platform.common.ui.callbacks import build_callback, parse_callback
from vpn_bot_platform.common.ui.keyboards import (
    broadcast_actions,
    cancel_only_keyboard,
    confirm_keyboard,
    discount_actions,
    external_template_actions,
    forced_join_menu,
    inline_keyboard,
    master_main_menu,
    master_section_menu,
    master_seller_bot_actions,
    panel_actions,
    panel_list_menu,
    paginate,
    plan_actions,
    reseller_list_menu,
    reseller_detail_actions,
    reseller_actions,
    seller_bot_more_menu,
    seller_bot_list_menu,
    seller_bot_provision_success_menu,
    seller_bot_type_menu,
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
    bot_type = State()
    owner_telegram_id = State()
    owner_username = State()
    owner_display_name = State()
    name = State()
    token = State()
    panel_name = State()
    panel_base_url = State()
    panel_auth_type = State()
    panel_username = State()
    panel_password = State()
    panel_token = State()
    panel_admin = State()
    volume = State()
    confirm = State()


class SellerBotSearchStates(StatesGroup):
    query = State()


class SellerBotVolumeEditStates(StatesGroup):
    volume = State()


class SellerBotVolumeAddStates(StatesGroup):
    amount = State()
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


class ReportCustomStates(StatesGroup):
    days = State()


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


class PanelPasswordEditStates(StatesGroup):
    password = State()
    confirm = State()


class PanelTokenEditStates(StatesGroup):
    token = State()
    confirm = State()


class PanelAssignmentCreateStates(StatesGroup):
    reseller = State()
    panel = State()
    admin_username = State()
    priority = State()
    weight = State()
    confirm = State()


class PanelAssignmentRoutingStates(StatesGroup):
    priority = State()
    weight = State()
    confirm = State()


class ForcedJoinCreateStates(StatesGroup):
    chat_id = State()
    title = State()
    confirm = State()


class ForcedJoinRemoveStates(StatesGroup):
    chat_id = State()
    confirm = State()


def _parse_args(raw: str | None) -> list[str]:
    try:
        return shlex.split(raw or "")
    except ValueError:
        return []


def _panel_auth_type(panel) -> str:
    return "token" if panel.token_encrypted else "password"


def _panel_error_message(error: ValueError) -> str:
    messages = {
        "panel_credentials_required": "Panel credentials are required.",
        "panel_base_url_invalid": "Send a valid URL starting with http:// or https://.",
        "panel_base_url_exists": "This panel URL is already registered.",
        "panel_not_found": "Panel not found.",
        "panel_password_required": "Panel password is required.",
        "panel_token_required": "Panel token is required.",
        "panel_token_auth_only": "This panel uses token auth. Change the token instead.",
        "panel_password_auth_only": "This panel uses username/password auth.",
        "reseller_already_exists": "This Telegram ID already owns a reseller account.",
        "reseller_not_found": "Reseller not found.",
    }
    return messages.get(str(error), str(error))


def _bundle_error_message(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return _panel_error_message(exc)
    return str(exc)


def _sellerbot_panel_auth_keyboard() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [("Panel token auth", build_callback("m", "sellerbot_panel_auth", "token"))],
            [("Panel login auth", build_callback("m", "sellerbot_panel_auth", "password"))],
            [("Cancel", build_callback("m", "sellerbot_cancel"))],
        ]
    )


def _normalize_telegram_username(raw: str) -> str:
    value = raw.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", value):
        raise ValueError("invalid_telegram_username")
    return value


def _username_error_message() -> str:
    return "یوزرنیم معتبر نیست. مثال: sina_azad (بدون @، حداقل ۵ کاراکتر)"


async def _show_add_seller_bot_start(
    message: Message,
    state: FSMContext,
    reseller_service: ResellerService,
) -> None:
    await state.clear()
    templates = await reseller_service.list_external_bot_templates()
    await state.set_state(SellerBotCreateStates.bot_type)
    await message.answer(
        "\n".join(
            [
                title("ربات جدید"),
                "مالک، پنل مرزبان و ربات در یک مرحله ساخته می‌شوند.",
                "",
                "نوع ربات را انتخاب کنید:",
            ]
        ),
        reply_markup=seller_bot_type_menu(has_external_templates=bool(templates)),
    )


async def _edit_add_seller_bot_start(
    callback: CallbackQuery,
    state: FSMContext,
    reseller_service: ResellerService,
) -> None:
    if callback.message is None:
        return
    await state.clear()
    templates = await reseller_service.list_external_bot_templates()
    await state.set_state(SellerBotCreateStates.bot_type)
    await callback.message.edit_text(
        "\n".join(
            [
                title("ربات جدید"),
                "مالک، پنل مرزبان و ربات در یک مرحله ساخته می‌شوند.",
                "",
                "نوع ربات را انتخاب کنید:",
            ]
        ),
        reply_markup=seller_bot_type_menu(has_external_templates=bool(templates)),
    )


async def _edit_sellerbot_owner_step(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await state.set_state(SellerBotCreateStates.owner_telegram_id)
    await callback.message.edit_text(
        "\n".join(
            [
                title("ربات جدید"),
                "آیدی عددی تلگرام مالک ربات را بفرستید.",
                "",
                "این شخص ادمین ربات فروشنده می‌شود.",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


async def _edit_sellerbot_owner_username_step(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await state.set_state(SellerBotCreateStates.owner_username)
    await callback.message.edit_text(
        "\n".join(
            [
                title("ربات جدید"),
                "یوزرنیم تلگرام مالک را بفرستید (با یا بدون @).",
                "",
                "مثال: sina_azad",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


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


@router.message(F.text.in_({"🏠 منوی اصلی", "منوی اصلی", "ربات های فروشنده", "ربات‌های فروشنده", "افزودن ربات فروشنده", "ربات جدید"}))
async def master_reply_menu_alias(
    message: Message,
    reseller_service: ResellerService,
    state: FSMContext,
) -> None:
    await state.clear()
    if message.text in {"ربات های فروشنده", "ربات‌های فروشنده"}:
        seller_bots = [
            seller_bot
            for seller_bot in await reseller_service.list_seller_bots()
            if seller_bot.status != "disabled"
        ]
        page = paginate(seller_bots, page=1, per_page=5)
        labels = await _seller_bot_list_labels(reseller_service, list(page.items))
        await message.answer(
            await _seller_bots_page_text(reseller_service, page),
            reply_markup=seller_bot_list_menu(
                page=page.page,
                total_pages=page.total_pages,
                seller_bots=list(page.items),
                labels=labels,
            ),
        )
        return
    if message.text in {"افزودن ربات فروشنده", "ربات جدید"}:
        await _show_add_seller_bot_start(message, state, reseller_service)
        return
    await message.answer(_master_dashboard_text(), reply_markup=master_main_menu())


@router.message(
    F.text.in_(
        {
            "Seller Bots",
            "Add Seller Bot",
            "Resellers",
            "Panels",
            "Plans",
            "Reports",
            "Settings",
        }
    )
)
async def master_reply_menu_alias_english(
    message: Message,
    reseller_service: ResellerService,
    state: FSMContext,
) -> None:
    await state.clear()
    if message.text == "Seller Bots":
        seller_bots = [
            seller_bot
            for seller_bot in await reseller_service.list_seller_bots()
            if seller_bot.status != "disabled"
        ]
        page = paginate(seller_bots, page=1, per_page=5)
        labels = await _seller_bot_list_labels(reseller_service, list(page.items))
        await message.answer(
            await _seller_bots_page_text(reseller_service, page),
            reply_markup=seller_bot_list_menu(
                page=page.page,
                total_pages=page.total_pages,
                seller_bots=list(page.items),
                labels=labels,
            ),
        )
    elif message.text == "Add Seller Bot":
        await _show_add_seller_bot_start(message, state, reseller_service)
    elif message.text == "Resellers":
        resellers = await reseller_service.list_resellers()
        page = _paginate_resellers(resellers, page=1)
        await message.answer(
            _resellers_page_text(page),
            reply_markup=reseller_list_menu(
                page=page.page,
                total_pages=page.total_pages,
                resellers=list(page.items),
            ),
        )
    elif message.text == "Panels":
        panels = await reseller_service.list_marzban_panels()
        await message.answer(
            await _panels_text(reseller_service),
            reply_markup=panel_list_menu(panels=panels[:20]),
        )
    elif message.text == "Plans":
        await message.answer(await _plans_text(reseller_service), reply_markup=master_section_menu("plans"))
    elif message.text == "Reports":
        report = await reseller_service.global_report(days=1)
        await message.answer(_format_report("Global Report - Today", report), reply_markup=master_section_menu("reports"))
    elif message.text == "Settings":
        await message.answer(
            "\n".join([title("تنظیمات"), "تنظیمات پیشرفته پلتفرم."]),
            reply_markup=master_section_menu("platform_settings"),
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
    elif action.action == "platform_settings":
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("تنظیمات"),
                    "فروشنده‌ها، پنل‌ها و تنظیمات پیشرفته.",
                ]
            ),
            reply_markup=master_section_menu("platform_settings"),
        )
    elif action.action == "platform_more":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("سایر تنظیمات"), "پلن، تخفیف و پیام همگانی."]),
            reply_markup=master_section_menu("platform_more"),
        )
    elif action.action == "resellers":
        page_number = _parse_positive_int(action.value) or 1
        resellers = await reseller_service.list_resellers()
        page = _paginate_resellers(resellers, page=page_number)
        await callback.message.edit_text(
            _resellers_page_text(page),
            reply_markup=reseller_list_menu(
                page=page.page,
                total_pages=page.total_pages,
                resellers=list(page.items),
            ),
        )
    elif action.action in {"reseller_detail", "reseller_seller_bots", "reseller_plans", "reseller_panels"}:
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller.", show_alert=True)
            return
        reseller = await _find_reseller_by_telegram_id(reseller_service, telegram_id=int(action.value))
        if reseller is None:
            await callback.answer("Reseller not found.", show_alert=True)
            return
        if action.action == "reseller_detail":
            text = await _reseller_detail_text(reseller_service, reseller)
        elif action.action == "reseller_seller_bots":
            text = await _reseller_seller_bots_text(reseller_service, reseller)
            seller_bots = [
                item for item in await reseller_service.list_seller_bots() if item.reseller_id == reseller.id
            ]
            reply_markup = (
                _reseller_seller_bots_keyboard(seller_bots)
                if seller_bots
                else reseller_detail_actions(reseller.telegram_user_id)
            )
            await callback.message.edit_text(text, reply_markup=reply_markup)
            await callback.answer()
            return
        elif action.action == "reseller_plans":
            text = await _reseller_plans_text(reseller_service, reseller)
        else:
            text = await _reseller_panels_text(reseller_service, reseller)
        await callback.message.edit_text(
            text,
            reply_markup=reseller_detail_actions(reseller.telegram_user_id),
        )
        if action.action == "reseller_panels":
            assignments = await reseller_service.list_panel_assignments_for_reseller(reseller_id=reseller.id)
            for item in assignments[:5]:
                await callback.message.answer(
                    _panel_assignment_detail_text(item.assignment),
                    reply_markup=_panel_assignment_actions(item.assignment.id, reseller.telegram_user_id),
                )
    elif action.action == "reseller_status_menu":
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Reseller Status"),
                    f"Telegram: {action.value}",
                    "",
                    "Choose the new status.",
                ]
            ),
            reply_markup=reseller_actions(int(action.value)),
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
        page_number = _parse_positive_int(action.value) or 1
        seller_bots = [
            seller_bot
            for seller_bot in await reseller_service.list_seller_bots()
            if seller_bot.status != "disabled"
        ]
        page = paginate(seller_bots, page=page_number, per_page=5)
        labels = await _seller_bot_list_labels(reseller_service, list(page.items))
        await callback.message.edit_text(
            await _seller_bots_page_text(reseller_service, page),
            reply_markup=seller_bot_list_menu(
                page=page.page,
                total_pages=page.total_pages,
                seller_bots=list(page.items),
                labels=labels,
            ),
        )
    elif action.action == "seller_select":
        seller_bot = await _find_seller_bot(reseller_service, seller_bot_id=action.value or "")
        if seller_bot is None:
            await callback.answer("Seller bot not found.", show_alert=True)
            return
        await callback.message.edit_text(
            await _seller_bot_card_text(reseller_service, seller_bot),
            reply_markup=master_seller_bot_actions(seller_bot.id),
        )
    elif action.action == "add_seller_bot":
        await _edit_add_seller_bot_start(callback, state, reseller_service)
    elif action.action == "seller_search":
        await state.clear()
        await state.set_state(SellerBotSearchStates.query)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Search Seller Bots"),
                    "Send bot name, short ID, full ID, status, or container name.",
                ]
            ),
            reply_markup=master_section_menu("seller_bots"),
        )
    elif action.action == "seller_volume_edit":
        seller_bot = await _find_seller_bot(reseller_service, seller_bot_id=action.value or "")
        if seller_bot is None:
            await callback.answer("Seller bot not found.", show_alert=True)
            return
        await state.clear()
        await state.set_state(SellerBotVolumeEditStates.volume)
        await state.update_data(seller_volume_bot_id=seller_bot.id)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Set Seller Bot GB Limit"),
                    f"Bot: {seller_bot.name}",
                    f"Current limit: {_seller_bot_volume_text(seller_bot)}",
                    "",
                    "Send the total GB limit for this seller bot.",
                    "Use 0 to stop new sales.",
                ]
            ),
            reply_markup=master_seller_bot_actions(seller_bot.id),
        )
    elif action.action == "seller_volume_add":
        seller_bot = await _find_seller_bot(reseller_service, seller_bot_id=action.value or "")
        if seller_bot is None:
            await callback.answer("Seller bot not found.", show_alert=True)
            return
        quota = await reseller_service.seller_bot_quota(seller_bot_id=seller_bot.id)
        await state.clear()
        await state.set_state(SellerBotVolumeAddStates.amount)
        await state.update_data(seller_volume_bot_id=seller_bot.id)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Add Seller Bot GB"),
                    f"Bot: {seller_bot.name}",
                    f"Current limit: {_quota_value_text(quota.limit_gb)}",
                    f"Used: {quota.used_gb} GB",
                    f"Reserved: {quota.reserved_gb} GB",
                    f"Remaining: {_quota_value_text(quota.remaining_gb)}",
                    "",
                    "Send the GB amount to add.",
                    "Example: 100",
                ]
            ),
            reply_markup=master_seller_bot_actions(seller_bot.id),
        )
    elif action.action in {"seller_config_panel", "seller_config_pricing", "seller_config_admins"}:
        seller_bot = await _find_seller_bot(reseller_service, seller_bot_id=action.value or "")
        if seller_bot is None:
            await callback.answer("Seller bot not found.", show_alert=True)
            return
        reseller = await _find_reseller_by_id(reseller_service, reseller_id=seller_bot.reseller_id)
        if reseller is None:
            await callback.answer("Seller bot owner not found.", show_alert=True)
            return
        if action.action == "seller_config_panel":
            text = await _reseller_panels_text(reseller_service, reseller)
        elif action.action == "seller_config_pricing":
            text = await _reseller_plans_text(reseller_service, reseller)
        else:
            text = _seller_bot_admins_text(seller_bot, reseller)
        await callback.message.edit_text(text, reply_markup=master_seller_bot_actions(seller_bot.id))
    elif action.action == "seller_delete_confirm":
        seller_bot = await _find_seller_bot(reseller_service, seller_bot_id=action.value or "")
        if seller_bot is None:
            await callback.answer("Seller bot not found.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Delete Seller Bot"),
                    f"Name: {seller_bot.name}",
                    f"ID: {seller_bot.id}",
                    "",
                    "This disables the seller bot and removes it from the active seller-bot list.",
                    "Platform buyers, orders, payments, wallet transactions, and VPN services stay in Postgres.",
                ]
            ),
            reply_markup=confirm_keyboard(
                scope="m",
                confirm_action="seller_delete_apply",
                cancel_action="seller_detail",
                value=seller_bot.id,
            ),
        )
    elif action.action == "seller_delete_apply":
        if not action.value:
            await callback.answer("Seller bot is missing.", show_alert=True)
            return
        try:
            seller_bot = await reseller_service.delete_seller_bot(
                seller_bot_id=action.value,
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError:
            await callback.answer("Seller bot not found.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Seller Bot Deleted"),
                    f"Name: {seller_bot.name}",
                    f"ID: {seller_bot.id}",
                    f"Status: {status_label(seller_bot.status)}",
                    f"Last error: {seller_bot.last_error or '-'}",
                ]
            ),
            reply_markup=master_section_menu("seller_bots"),
        )
    elif action.action == "external_bots":
        await callback.message.edit_text(
            await _external_bots_text(reseller_service),
            reply_markup=master_section_menu("external_bots"),
        )
        for template in (await reseller_service.list_external_bot_templates())[:5]:
            await callback.message.answer(
                _external_template_text(template),
                reply_markup=external_template_actions(template.id),
            )
    elif action.action == "ext_sync":
        if not action.value:
            await callback.answer("Template is missing.", show_alert=True)
            return
        try:
            result = await reseller_service.sync_external_bot_template(
                template_id_or_key=action.value,
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError:
            await callback.answer("External template not found.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("External Bot Template Sync"),
                    f"Name: {result.template.name}",
                    f"Key: {result.template.key}",
                    f"Status: {'OK' if result.ok else 'Failed'}",
                    f"Result: {result.message}",
                ]
            ),
            reply_markup=external_template_actions(result.template.id),
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
                quota = await reseller_service.seller_bot_quota(seller_bot_id=seller_bot.id)
                resellers = await reseller_service.list_resellers()
                reseller = next((item for item in resellers if item.id == seller_bot.reseller_id), None)
                text = "\n".join(
                    [
                        title("Seller Bot Detail"),
                        f"Name: {seller_bot.name}",
                        f"ID: {seller_bot.id}",
                        f"Reseller: {reseller.display_name if reseller else short_id(seller_bot.reseller_id)}",
                        f"Status: {status_label(seller_bot.status)}",
                        f"Volume limit: {_quota_value_text(quota.limit_gb)}",
                        f"Used: {quota.used_gb} GB",
                        f"Reserved: {quota.reserved_gb} GB",
                        f"Remaining: {_quota_value_text(quota.remaining_gb)}",
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
    elif action.action == "seller_more":
        seller_bot = await _find_seller_bot(reseller_service, seller_bot_id=action.value or "")
        if seller_bot is None:
            await callback.answer("ربات پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("تنظیمات بیشتر"),
                    f"ربات: {seller_bot.name}",
                ]
            ),
            reply_markup=seller_bot_more_menu(seller_bot.id),
        )
    elif action.action == "panels":
        await state.clear()
        panels = await reseller_service.list_marzban_panels()
        await callback.message.edit_text(
            await _panels_text(reseller_service),
            reply_markup=panel_list_menu(panels=panels[:20]),
        )
    elif action.action == "panel_detail":
        if not action.value:
            await callback.answer("Panel is missing.", show_alert=True)
            return
        try:
            detail = await reseller_service.get_panel_detail(panel_id=action.value)
        except ValueError:
            await callback.answer("Panel not found.", show_alert=True)
            return
        await callback.message.edit_text(
            _panel_detail_text(detail),
            reply_markup=panel_actions(detail.panel.id, auth_type=detail.auth_type),
        )
    elif action.action == "panel_test":
        if not action.value:
            await callback.answer("Panel is missing.", show_alert=True)
            return
        try:
            result = await reseller_service.test_panel_connection(panel_id=action.value)
        except ValueError:
            await callback.answer("Panel not found.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Panel Test"),
                    f"Name: {result.panel.name}",
                    f"Status: {status_label('active' if result.panel.is_active else 'disabled')}",
                    f"Result: {status_label('active' if result.ok else 'failed')}",
                    f"Message: {result.message}",
                ]
            ),
            reply_markup=panel_actions(result.panel.id, auth_type=_panel_auth_type(result.panel)),
        )
    elif action.action == "panel_disable_confirm":
        if not action.value:
            await callback.answer("Panel is missing.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Disable Panel"),
                    f"Panel ID: {action.value}",
                    "",
                    "Confirm only if this panel should stop receiving new provisioning.",
                ]
            ),
            reply_markup=confirm_keyboard(
                scope="m",
                confirm_action="panel_disable_apply",
                cancel_action="panels",
                value=action.value,
            ),
        )
    elif action.action == "panel_disable_apply":
        if not action.value:
            await callback.answer("Panel is missing.", show_alert=True)
            return
        try:
            detail = await reseller_service.disable_panel(
                panel_id=action.value,
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError:
            await callback.answer("Panel not found.", show_alert=True)
            return
        await callback.message.edit_text(
            _panel_detail_text(detail),
            reply_markup=panel_actions(detail.panel.id, auth_type=detail.auth_type),
        )
    elif action.action == "panel_change_password":
        if not action.value:
            await callback.answer("Panel is missing.", show_alert=True)
            return
        try:
            detail = await reseller_service.get_panel_detail(panel_id=action.value)
        except ValueError:
            await callback.answer("Panel not found.", show_alert=True)
            return
        if detail.auth_type == "token":
            await callback.answer("This panel uses token auth.", show_alert=True)
            return
        await state.clear()
        await state.update_data(panel_credentials_panel_id=detail.panel.id)
        await state.set_state(PanelPasswordEditStates.password)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Change Panel Password"),
                    f"Panel: {detail.panel.name}",
                    "",
                    "Send the new Marzban admin password.",
                    "It will be encrypted and hidden in the preview.",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_edit_cancel"),
        )
        await callback.answer()
    elif action.action == "panel_change_token":
        if not action.value:
            await callback.answer("Panel is missing.", show_alert=True)
            return
        try:
            detail = await reseller_service.get_panel_detail(panel_id=action.value)
        except ValueError:
            await callback.answer("Panel not found.", show_alert=True)
            return
        if detail.auth_type != "token":
            await callback.answer("This panel uses username/password auth.", show_alert=True)
            return
        await state.clear()
        await state.update_data(panel_credentials_panel_id=detail.panel.id)
        await state.set_state(PanelTokenEditStates.token)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Change Panel Token"),
                    f"Panel: {detail.panel.name}",
                    "",
                    "Send the new Marzban admin token.",
                    "It will be encrypted and hidden in the preview.",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_token_edit_cancel"),
        )
        await callback.answer()
    elif action.action == "panel_password_edit_apply":
        data = await state.get_data()
        panel_id = str(data.get("panel_credentials_panel_id") or "")
        password = str(data.get("panel_password_edit_value") or "").strip()
        if not panel_id or not password:
            await callback.answer("Password update draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            detail = await reseller_service.update_panel_password(
                panel_id=panel_id,
                password=password,
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError as exc:
            await callback.answer(_panel_error_message(exc), show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Panel Password Updated"), f"Panel: {detail.panel.name}"]),
            reply_markup=panel_actions(detail.panel.id, auth_type=detail.auth_type),
        )
        await callback.answer()
    elif action.action == "panel_token_edit_apply":
        data = await state.get_data()
        panel_id = str(data.get("panel_credentials_panel_id") or "")
        token_value = str(data.get("panel_token_edit_value") or "").strip()
        if not panel_id or not token_value:
            await callback.answer("Token update draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            detail = await reseller_service.update_panel_token(
                panel_id=panel_id,
                token=token_value,
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError as exc:
            await callback.answer(_panel_error_message(exc), show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Panel Token Updated"), f"Panel: {detail.panel.name}"]),
            reply_markup=panel_actions(detail.panel.id, auth_type=detail.auth_type),
        )
        await callback.answer()
    elif action.action == "panel_password_edit_cancel":
        panel_id = str((await state.get_data()).get("panel_credentials_panel_id") or "")
        await state.clear()
        if panel_id:
            try:
                detail = await reseller_service.get_panel_detail(panel_id=panel_id)
            except ValueError:
                await callback.message.edit_text(
                    "\n".join([title("Password Update Canceled"), "No panel was changed."]),
                    reply_markup=master_section_menu("panels"),
                )
            else:
                await callback.message.edit_text(
                    _panel_detail_text(detail),
                    reply_markup=panel_actions(detail.panel.id, auth_type=detail.auth_type),
                )
        else:
            await callback.message.edit_text(
                "\n".join([title("Password Update Canceled"), "No panel was changed."]),
                reply_markup=master_section_menu("panels"),
            )
        await callback.answer()
    elif action.action == "panel_token_edit_cancel":
        panel_id = str((await state.get_data()).get("panel_credentials_panel_id") or "")
        await state.clear()
        if panel_id:
            try:
                detail = await reseller_service.get_panel_detail(panel_id=panel_id)
            except ValueError:
                await callback.message.edit_text(
                    "\n".join([title("Token Update Canceled"), "No panel was changed."]),
                    reply_markup=master_section_menu("panels"),
                )
            else:
                await callback.message.edit_text(
                    _panel_detail_text(detail),
                    reply_markup=panel_actions(detail.panel.id, auth_type=detail.auth_type),
                )
        else:
            await callback.message.edit_text(
                "\n".join([title("Token Update Canceled"), "No panel was changed."]),
                reply_markup=master_section_menu("panels"),
            )
        await callback.answer()
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
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_token_cancel"),
        )
        await callback.answer()
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
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_cancel"),
        )
        await callback.answer()
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
            await callback.answer(_panel_error_message(exc), show_alert=True)
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
            reply_markup=panel_actions(panel.id, auth_type="token"),
        )
        await callback.answer()
    elif action.action == "panel_token_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Panel Canceled"), "No panel was registered."]),
            reply_markup=master_section_menu("panels"),
        )
        await callback.answer()
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
            await callback.answer(_panel_error_message(exc), show_alert=True)
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
            reply_markup=panel_actions(panel.id, auth_type="password"),
        )
        await callback.answer()
    elif action.action == "panel_password_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Panel Canceled"), "No panel was registered."]),
            reply_markup=master_section_menu("panels"),
        )
        await callback.answer()
    elif action.action == "guide_assign_panel":
        await state.clear()
        resellers = await reseller_service.list_resellers()
        panels = await reseller_service.list_marzban_panels()
        if not resellers:
            await callback.message.edit_text(
                "\n".join([title("Assign Panel"), "Create a reseller first."]),
                reply_markup=master_section_menu("panels"),
            )
            return
        if not panels:
            await callback.message.edit_text(
                "\n".join([title("Assign Panel"), "Register a Marzban panel first."]),
                reply_markup=master_section_menu("panels"),
            )
            return
        await state.set_state(PanelAssignmentCreateStates.reseller)
        await callback.message.edit_text(
            "\n".join([title("Assign Panel"), "Select the reseller."]),
            reply_markup=_reseller_select_keyboard(
                resellers[:10],
                action_name="panel_assign_reseller",
                cancel_action="panel_assign_cancel",
            ),
        )
    elif action.action == "panel_assign_reseller":
        if not action.value or not action.value.isdigit():
            await callback.answer("Invalid reseller.", show_alert=True)
            return
        panels = await reseller_service.list_marzban_panels()
        if not panels:
            await callback.message.edit_text(
                "\n".join([title("Assign Panel"), "Register a Marzban panel first."]),
                reply_markup=master_section_menu("panels"),
            )
            return
        await state.update_data(panel_assign_reseller_telegram_id=int(action.value))
        await state.set_state(PanelAssignmentCreateStates.panel)
        await callback.message.edit_text(
            "\n".join([title("Assign Panel"), "Select the Marzban panel."]),
            reply_markup=_panel_select_keyboard(
                panels[:10],
                action_name="panel_assign_panel",
                cancel_action="panel_assign_cancel",
            ),
        )
    elif action.action == "panel_assign_panel":
        if not action.value:
            await callback.answer("Invalid panel.", show_alert=True)
            return
        await state.update_data(panel_assign_panel_id=action.value)
        await state.set_state(PanelAssignmentCreateStates.admin_username)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Assign Panel"),
                    "Send the optional Marzban admin username.",
                    "",
                    "Send - to skip.",
                ]
            ),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "panel_assign_create":
        data = await state.get_data()
        reseller_telegram_id = data.get("panel_assign_reseller_telegram_id")
        panel_id = str(data.get("panel_assign_panel_id") or "").strip()
        admin_username = str(data.get("panel_assign_admin_username") or "").strip() or None
        priority = data.get("panel_assign_priority")
        weight = data.get("panel_assign_weight")
        if not reseller_telegram_id or not panel_id or priority is None or weight is None:
            await callback.answer("Panel assignment draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            assignment = await reseller_service.assign_panel(
                reseller_telegram_id=int(reseller_telegram_id),
                panel_id=panel_id,
                marzban_admin_username=admin_username,
                priority=int(priority),
                weight=int(weight),
            )
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            _panel_assignment_detail_text(assignment),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "panel_assign_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Assignment Canceled"), "No panel assignment was created."]),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "panel_routing_edit":
        if not action.value:
            await callback.answer("Assignment is missing.", show_alert=True)
            return
        await state.clear()
        await state.update_data(panel_routing_assignment_id=action.value)
        await state.set_state(PanelAssignmentRoutingStates.priority)
        await callback.message.edit_text(
            "\n".join([title("Edit Panel Routing"), "Send the new priority. Lower priority is tried first."]),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "panel_routing_update":
        data = await state.get_data()
        assignment_id = str(data.get("panel_routing_assignment_id") or "").strip()
        priority = data.get("panel_routing_priority")
        weight = data.get("panel_routing_weight")
        if not assignment_id or priority is None or weight is None:
            await callback.answer("Routing draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            assignment = await reseller_service.update_panel_assignment_routing(
                assignment_id=assignment_id,
                priority=int(priority),
                weight=int(weight),
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError:
            await callback.answer("Assignment not found.", show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            _panel_assignment_detail_text(assignment),
            reply_markup=_panel_assignment_actions(assignment.id),
        )
    elif action.action == "panel_routing_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("Routing Canceled"), "No panel assignment was changed."]),
            reply_markup=master_section_menu("panels"),
        )
    elif action.action == "plans":
        await callback.message.edit_text(
            await _plans_text(reseller_service),
            reply_markup=master_section_menu("plans"),
        )
        for plan in (await reseller_service.list_plans())[:5]:
            await callback.message.answer(
                _plan_card_text(plan),
                reply_markup=plan_actions(plan.id, is_active=plan.is_active),
            )
    elif action.action == "plan_detail":
        if not action.value:
            await callback.answer("Plan is missing.", show_alert=True)
            return
        try:
            plan = await reseller_service.get_plan(plan_id=action.value)
        except ValueError:
            await callback.answer("Plan not found.", show_alert=True)
            return
        await callback.message.edit_text(
            _plan_detail_text(plan),
            reply_markup=plan_actions(plan.id, is_active=plan.is_active),
        )
    elif action.action == "plan_disable_confirm":
        if not action.value:
            await callback.answer("Plan is missing.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join([title("Disable Plan"), f"Plan ID: {action.value}", "", "Confirm to hide this plan from buyers."]),
            reply_markup=confirm_keyboard(
                scope="m",
                confirm_action="plan_disable_apply",
                cancel_action="plans",
                value=action.value,
            ),
        )
    elif action.action in {"plan_disable_apply", "plan_enable"}:
        if not action.value:
            await callback.answer("Plan is missing.", show_alert=True)
            return
        try:
            plan = await reseller_service.set_plan_status(
                plan_id=action.value,
                is_active=action.action == "plan_enable",
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError:
            await callback.answer("Plan not found.", show_alert=True)
            return
        await callback.message.edit_text(
            _plan_detail_text(plan),
            reply_markup=plan_actions(plan.id, is_active=plan.is_active),
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
        for discount in (await reseller_service.list_discounts())[:5]:
            await callback.message.answer(
                _discount_card_text(discount),
                reply_markup=discount_actions(discount.id, is_active=discount.is_active),
            )
    elif action.action == "discount_detail":
        if not action.value:
            await callback.answer("Discount is missing.", show_alert=True)
            return
        try:
            discount = await reseller_service.get_discount(discount_id=action.value)
        except ValueError:
            await callback.answer("Discount not found.", show_alert=True)
            return
        await callback.message.edit_text(
            _discount_detail_text(discount),
            reply_markup=discount_actions(discount.id, is_active=discount.is_active),
        )
    elif action.action == "discount_disable_confirm":
        if not action.value:
            await callback.answer("Discount is missing.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join([title("Disable Discount"), f"Discount ID: {action.value}", "", "Confirm to stop accepting this code."]),
            reply_markup=confirm_keyboard(
                scope="m",
                confirm_action="discount_disable_apply",
                cancel_action="discounts",
                value=action.value,
            ),
        )
    elif action.action in {"discount_disable_apply", "discount_enable"}:
        if not action.value:
            await callback.answer("Discount is missing.", show_alert=True)
            return
        try:
            discount = await reseller_service.set_discount_status(
                discount_id=action.value,
                is_active=action.action == "discount_enable",
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError:
            await callback.answer("Discount not found.", show_alert=True)
            return
        await callback.message.edit_text(
            _discount_detail_text(discount),
            reply_markup=discount_actions(discount.id, is_active=discount.is_active),
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
            reply_markup=master_section_menu("reports"),
        )
    elif action.action == "report_custom":
        await state.clear()
        await state.set_state(ReportCustomStates.days)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Custom Report"),
                    "Send the number of days to include.",
                    "",
                    "Example: 14",
                ]
            ),
            reply_markup=master_section_menu("reports"),
        )
    elif action.action == "broadcasts":
        await callback.message.edit_text(
            await _broadcast_history_text(reseller_service),
            reply_markup=master_section_menu("broadcasts"),
        )
        for broadcast in (await reseller_service.list_global_broadcasts(limit=5)):
            await callback.message.answer(
                _broadcast_card_text(broadcast),
                reply_markup=broadcast_actions(broadcast.id, status=broadcast.status),
            )
    elif action.action == "broadcast_history":
        await callback.message.edit_text(
            await _broadcast_history_text(reseller_service),
            reply_markup=master_section_menu("broadcasts"),
        )
        for broadcast in (await reseller_service.list_global_broadcasts(limit=5)):
            await callback.message.answer(
                _broadcast_card_text(broadcast),
                reply_markup=broadcast_actions(broadcast.id, status=broadcast.status),
            )
    elif action.action == "broadcast_detail":
        if not action.value:
            await callback.answer("Broadcast is missing.", show_alert=True)
            return
        try:
            broadcast = await reseller_service.get_global_broadcast(broadcast_id=action.value)
        except ValueError:
            await callback.answer("Broadcast not found.", show_alert=True)
            return
        await callback.message.edit_text(
            _broadcast_detail_text(broadcast),
            reply_markup=broadcast_actions(broadcast.id, status=broadcast.status),
        )
    elif action.action == "broadcast_send_confirm":
        if not action.value:
            await callback.answer("Broadcast is missing.", show_alert=True)
            return
        try:
            draft = await reseller_service.get_global_broadcast_recipients(broadcast_id=action.value)
        except ValueError:
            await callback.answer("Broadcast not found.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Send Broadcast"),
                    f"ID: {draft.broadcast.id}",
                    f"Title: {draft.broadcast.title}",
                    f"Pending targets: {len(draft.recipients)}",
                    "",
                    "Confirm to send this message to all pending recipients.",
                ]
            ),
            reply_markup=confirm_keyboard(
                scope="m",
                confirm_action="broadcast_send_apply",
                cancel_action="broadcast_history",
                value=draft.broadcast.id,
            ),
        )
    elif action.action == "broadcast_send_apply":
        if not action.value:
            await callback.answer("Broadcast is missing.", show_alert=True)
            return
        try:
            draft = await reseller_service.get_global_broadcast_recipients(broadcast_id=action.value)
        except ValueError:
            await callback.answer("Broadcast not found.", show_alert=True)
            return
        delivered: set[int] = set()
        for recipient in draft.recipients:
            try:
                await callback.bot.send_message(
                    recipient.telegram_user_id,
                    "\n".join([title(draft.broadcast.title), draft.broadcast.body]),
                )
            except TelegramAPIError:
                continue
            delivered.add(recipient.telegram_user_id)
        broadcast = await reseller_service.mark_global_broadcast_sent(
            broadcast_id=draft.broadcast.id,
            delivered_telegram_ids=delivered,
        )
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Broadcast Sent"),
                    f"ID: {broadcast.id}",
                    f"Delivered: {len(delivered)}/{draft.broadcast.target_count}",
                ]
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
            _settings_text(),
            reply_markup=master_section_menu("settings"),
        )
    elif action.action == "settings_forced_join":
        await callback.message.edit_text(
            await _forced_join_text(reseller_service),
            reply_markup=forced_join_menu(),
        )
    elif action.action in {"settings_rate_limits", "settings_trial", "settings_payments"}:
        await callback.message.edit_text(
            _settings_detail_text(action.action),
            reply_markup=master_section_menu("settings"),
        )
    elif action.action == "system":
        await callback.message.edit_text(
            await _system_text(reseller_service),
            reply_markup=master_section_menu("system"),
        )
    elif action.action in {"system_health", "system_version", "system_backup", "system_errors"}:
        await callback.message.edit_text(
            _system_detail_text(action.action),
            reply_markup=master_section_menu("system"),
        )
    elif action.action == "system_audit":
        await callback.message.edit_text(
            await _recent_audit_text(reseller_service),
            reply_markup=master_section_menu("system"),
        )
    elif action.action == "list_forced_join":
        await callback.message.edit_text(
            await _forced_join_text(reseller_service),
            reply_markup=forced_join_menu(),
        )
    elif action.action == "forced_join_add":
        await state.clear()
        await state.set_state(ForcedJoinCreateStates.chat_id)
        await callback.message.edit_text(
            "\n".join([title("Add Forced Join"), "Send the required chat ID or public @username."]),
            reply_markup=forced_join_menu(),
        )
    elif action.action == "forced_join_remove":
        await state.clear()
        await state.set_state(ForcedJoinRemoveStates.chat_id)
        await callback.message.edit_text(
            "\n".join([title("Remove Forced Join"), "Send the chat ID or @username to remove."]),
            reply_markup=forced_join_menu(),
        )
    elif action.action == "forced_join_create":
        data = await state.get_data()
        chat_id = str(data.get("forced_join_chat_id") or "").strip()
        chat_title = str(data.get("forced_join_title") or "").strip() or None
        if not chat_id:
            await callback.answer("Forced join draft is incomplete.", show_alert=True)
            await state.clear()
            return
        chats = await reseller_service.get_forced_join_chats()
        chats = [chat for chat in chats if chat.chat_id != chat_id]
        chats.append(ForcedJoinChat(chat_id=chat_id, title=chat_title))
        await reseller_service.set_forced_join_chats(chats=chats)
        await state.clear()
        await callback.message.edit_text(
            await _forced_join_text(reseller_service),
            reply_markup=forced_join_menu(),
        )
    elif action.action == "forced_join_remove_apply":
        data = await state.get_data()
        chat_id = str(data.get("forced_join_remove_chat_id") or "").strip()
        chats = [chat for chat in await reseller_service.get_forced_join_chats() if chat.chat_id != chat_id]
        await reseller_service.set_forced_join_chats(chats=chats)
        await state.clear()
        await callback.message.edit_text(
            await _forced_join_text(reseller_service),
            reply_markup=forced_join_menu(),
        )
    elif action.action in {"forced_join_cancel", "forced_join_remove_cancel"}:
        await state.clear()
        await callback.message.edit_text(
            await _forced_join_text(reseller_service),
            reply_markup=forced_join_menu(),
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
        await _edit_add_seller_bot_start(callback, state, reseller_service)
    elif action.action == "sellerbot_type":
        if action.value not in {"native", "external", "simple_seller"}:
            await callback.answer("Invalid bot type.", show_alert=True)
            return
        if action.value == "external":
            await callback.answer("External seller bots are not available in the unified wizard yet.", show_alert=True)
            return
        if action.value == "simple_seller":
            await state.update_data(
                sellerbot_runtime_type="native",
                sellerbot_template_key=None,
                sellerbot_ui_profile=SellerBotUiProfile.SIMPLE_SELLER.value,
            )
        else:
            await state.update_data(
                sellerbot_runtime_type="native",
                sellerbot_template_key=None,
                sellerbot_ui_profile=SellerBotUiProfile.PLATFORM.value,
            )
        await _edit_sellerbot_owner_step(callback, state)
    elif action.action == "sellerbot_panel_auth":
        if action.value not in {"token", "password"}:
            await callback.answer("Invalid panel auth type.", show_alert=True)
            return
        await state.update_data(sellerbot_panel_auth=action.value)
        if action.value == "token":
            await state.set_state(SellerBotCreateStates.panel_token)
            await callback.message.edit_text(
                "\n".join(
                    [
                        title("Add Seller Bot"),
                        "Send the Marzban admin token for this new panel.",
                        "",
                        "The token will be encrypted and hidden in the preview.",
                    ]
                ),
                reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
            )
        else:
            await state.set_state(SellerBotCreateStates.panel_username)
            await callback.message.edit_text(
                "\n".join([title("Add Seller Bot"), "Send the Marzban admin username for this new panel."]),
                reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
            )
        await callback.answer()
    elif action.action == "sellerbot_create":
        data = await state.get_data()
        owner_telegram_id = data.get("sellerbot_owner_telegram_id")
        owner_username = str(data.get("sellerbot_owner_username") or "").strip()
        owner_display_name = str(data.get("sellerbot_owner_display_name") or "").strip()
        bot_name = str(data.get("sellerbot_name") or "").strip()
        bot_token = str(data.get("sellerbot_token") or "").strip()
        ui_profile_value = str(data.get("sellerbot_ui_profile") or SellerBotUiProfile.PLATFORM.value)
        panel_name = str(data.get("sellerbot_panel_name") or "").strip()
        panel_base_url = str(data.get("sellerbot_panel_base_url") or "").strip()
        panel_auth = str(data.get("sellerbot_panel_auth") or "").strip()
        panel_username = str(data.get("sellerbot_panel_username") or "").strip() or None
        panel_password = str(data.get("sellerbot_panel_password") or "").strip() or None
        panel_token = str(data.get("sellerbot_panel_token") or "").strip() or None
        panel_admin = str(data.get("sellerbot_panel_admin") or "").strip() or None
        volume_limit_gb = data.get("sellerbot_volume_limit_gb")
        required = [
            owner_telegram_id,
            owner_username,
            owner_display_name,
            bot_name,
            bot_token,
            panel_name,
            panel_base_url,
            panel_auth,
        ]
        if not all(required):
            await callback.answer("Seller bot draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            seller_bot_ui_profile = SellerBotUiProfile(ui_profile_value)
        except ValueError:
            seller_bot_ui_profile = SellerBotUiProfile.PLATFORM
        try:
            result = await reseller_service.provision_seller_bot_bundle(
                reseller_telegram_id=int(owner_telegram_id),
                reseller_display_name=owner_display_name,
                reseller_username=owner_username,
                bot_name=bot_name,
                bot_token=bot_token,
                panel_name=panel_name,
                panel_base_url=panel_base_url,
                ui_profile=seller_bot_ui_profile,
                panel_username=panel_username if panel_auth == "password" else None,
                panel_password=panel_password if panel_auth == "password" else None,
                panel_token=panel_token if panel_auth == "token" else None,
                marzban_admin_username=panel_admin,
                volume_limit_gb=volume_limit_gb,
                actor_telegram_id=callback.from_user.id,
            )
        except ValueError as exc:
            await callback.answer(_bundle_error_message(exc), show_alert=True)
            await callback.message.edit_text(
                _sellerbot_confirm_text(data, error=_bundle_error_message(exc)),
                reply_markup=confirm_keyboard(
                    scope="m",
                    confirm_action="sellerbot_create",
                    cancel_action="sellerbot_cancel",
                ),
            )
            return
        except (TokenValidationError, RuntimeError) as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        seller_bot = result.seller_bot
        panel = result.panel
        start_status = "Auto-start: skipped"
        if reseller_service.settings and reseller_service.settings.auto_start_seller_on_create:
            try:
                seller_bot = await reseller_service.start_seller_bot(seller_bot_id=seller_bot.id)
                start_status = f"Auto-start: {status_label(seller_bot.status)}"
            except (ValueError, RuntimeError) as exc:
                start_status = f"Auto-start failed: {exc}"
        panel_test_status = "Panel test: skipped"
        try:
            panel_test = await reseller_service.test_panel_connection(panel_id=panel.id)
            panel_test_status = f"Panel test: {status_label('active' if panel_test.ok else 'failed')} ({panel_test.message})"
        except ValueError:
            panel_test_status = "Panel test: panel not found"
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Seller Bot Provisioned"),
                    f"ID: {seller_bot.id}",
                    f"Name: {seller_bot.name}",
                    f"Owner: {result.reseller.display_name} ({result.reseller.telegram_user_id})",
                    f"Panel: {panel.name}",
                    f"Status: {status_label(seller_bot.status)}",
                    f"Stock: {_seller_bot_volume_text(seller_bot)}",
                    start_status,
                    panel_test_status,
                    "",
                    "Super user is co-admin on this bot.",
                ]
            ),
            reply_markup=seller_bot_provision_success_menu(
                seller_bot_id=seller_bot.id,
                panel_id=panel.id,
            ),
        )
        await callback.answer()
    elif action.action == "seller_volume_add_confirm":
        data = await state.get_data()
        seller_bot_id = str(data.get("seller_volume_bot_id") or "")
        added_gb = data.get("seller_volume_add_gb")
        if not seller_bot_id or not isinstance(added_gb, int):
            await callback.answer("GB top-up draft is incomplete.", show_alert=True)
            await state.clear()
            return
        try:
            quota = await reseller_service.add_seller_bot_volume(
                seller_bot_id=seller_bot_id,
                added_gb=added_gb,
                actor_telegram_id=callback.from_user.id,
            )
            seller_bot = await _find_seller_bot(reseller_service, seller_bot_id=seller_bot_id)
        except ValueError:
            await callback.answer("Seller bot not found or GB amount is invalid.", show_alert=True)
            await state.clear()
            return
        await state.clear()
        notification_status = ""
        try:
            contact = await reseller_service.seller_bot_admin_contact(seller_bot_id=seller_bot_id)
            await callback.bot.send_message(
                contact.admin_telegram_id,
                "\n".join(
                    [
                        "ظرفیت فروش ربات شما افزایش یافت.",
                        f"ربات: {contact.seller_bot.name}",
                        f"حجم اضافه‌شده: {added_gb} گیگ",
                        f"سقف جدید: {_quota_value_text(quota.limit_gb)}",
                        f"مصرف‌شده: {quota.used_gb} گیگ",
                        f"باقی‌مانده: {_quota_value_text(quota.remaining_gb)}",
                        "",
                        "از پنل ادمین ربات فروشنده بخش ظرفیت فروش می‌توانید وضعیت را ببینید.",
                    ]
                ),
            )
            notification_status = "Admin notification: sent"
        except Exception:
            notification_status = "Admin notification: failed"
        await callback.message.edit_text(
            "\n".join(
                [
                    title("Seller Bot GB Added"),
                    f"Bot: {seller_bot.name if seller_bot else short_id(seller_bot_id)}",
                    f"Added: {added_gb} GB",
                    f"New limit: {_quota_value_text(quota.limit_gb)}",
                    f"Used: {quota.used_gb} GB",
                    f"Reserved: {quota.reserved_gb} GB",
                    f"Remaining: {_quota_value_text(quota.remaining_gb)}",
                    notification_status,
                ]
            ),
            reply_markup=master_seller_bot_actions(seller_bot_id),
        )
    elif action.action == "seller_volume_add_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("GB Add Canceled"), "No seller bot capacity was changed."]),
            reply_markup=master_section_menu("seller_bots"),
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


@router.message(SellerBotCreateStates.bot_type)
async def sellerbot_create_waiting_for_type(message: Message) -> None:
    await message.answer(
        "\n".join([title("Add Seller Bot"), "Choose the bot type using the buttons."])
    )


@router.message(SellerBotCreateStates.owner_telegram_id)
async def sellerbot_create_owner_telegram_id(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    if not raw_value.isdigit():
        await message.answer(
            "\n".join([title("ربات جدید"), "آیدی عددی تلگرام را بفرستید (فقط عدد)."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_owner_telegram_id=int(raw_value))
    await state.set_state(SellerBotCreateStates.owner_username)
    await message.answer(
        "\n".join(
            [
                title("ربات جدید"),
                "یوزرنیم تلگرام مالک را بفرستید (با یا بدون @).",
                "",
                "مثال: sina_azad",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.owner_username)
async def sellerbot_create_owner_username(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    try:
        username = _normalize_telegram_username(raw_value)
    except ValueError:
        await message.answer(
            "\n".join([title("ربات جدید"), _username_error_message()]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_owner_username=username)
    await state.set_state(SellerBotCreateStates.owner_display_name)
    await message.answer(
        "\n".join(
            [
                title("ربات جدید"),
                "نام نمایشی مالک را بفرستید.",
                "",
                "مثال: سینا آزاد",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.owner_display_name)
async def sellerbot_create_owner_display_name(message: Message, state: FSMContext) -> None:
    display_name = (message.text or "").strip()
    if not display_name or display_name.startswith("/"):
        await message.answer(
            "\n".join([title("ربات جدید"), "یک نام نمایشی برای مالک بفرستید."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_owner_display_name=display_name[:128])
    await state.set_state(SellerBotCreateStates.name)
    await message.answer(
        "\n".join(
            [
                title("ربات جدید"),
                "نام نمایشی ربات فروشنده را بفرستید.",
                "",
                "مثال: وی‌پی‌ان سینا",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.name)
async def sellerbot_create_name(message: Message, state: FSMContext) -> None:
    bot_name = (message.text or "").strip()
    if not bot_name or bot_name.startswith("/"):
        await message.answer(
            "\n".join(
                [
                    title("Add Seller Bot"),
                    "That was not a valid name.",
                    "",
                    "Type a plain display name, for example:",
                    "Sina Azad VPN",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_name=bot_name[:128])
    await state.set_state(SellerBotCreateStates.token)
    await message.answer(
        "\n".join(
            [
                title("Add Seller Bot"),
                "Paste the Telegram bot token from BotFather.",
                "",
                "Format example:",
                "123456789:ABCdef...",
                "",
                "The token will be encrypted and will not be shown again.",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.token)
async def sellerbot_create_token(message: Message, state: FSMContext) -> None:
    bot_token = (message.text or "").strip()
    try:
        validate_token(bot_token)
    except TokenValidationError as exc:
        await message.answer(
            "\n".join(
                [
                    title("Add Seller Bot"),
                    f"Invalid token: {exc}",
                    "",
                    "Paste the exact token from BotFather.",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_token=bot_token)
    await state.set_state(SellerBotCreateStates.panel_name)
    await message.answer(
        "\n".join(
            [
                title("Add Seller Bot"),
                "Send a short name for the new Marzban panel.",
                "",
                "Example: Germany Main",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.panel_name)
async def sellerbot_create_panel_name(message: Message, state: FSMContext) -> None:
    panel_name = (message.text or "").strip()
    if not panel_name or panel_name.startswith("/"):
        await message.answer(
            "\n".join([title("Add Seller Bot"), "Send a panel name, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_panel_name=panel_name[:128])
    await state.set_state(SellerBotCreateStates.panel_base_url)
    await message.answer(
        "\n".join(
            [
                title("Add Seller Bot"),
                "Send the Marzban base URL.",
                "",
                "Example: https://panel.example.com",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.panel_base_url)
async def sellerbot_create_panel_base_url(message: Message, state: FSMContext) -> None:
    base_url = (message.text or "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        await message.answer(
            "\n".join([title("Add Seller Bot"), "Send a valid URL starting with http:// or https://."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_panel_base_url=base_url)
    await state.set_state(SellerBotCreateStates.panel_auth_type)
    await message.answer(
        "\n".join([title("Add Seller Bot"), "Choose how this new panel authenticates."]),
        reply_markup=_sellerbot_panel_auth_keyboard(),
    )


@router.message(SellerBotCreateStates.panel_auth_type)
async def sellerbot_create_waiting_for_panel_auth(message: Message) -> None:
    await message.answer(
        "\n".join([title("Add Seller Bot"), "Choose panel auth using the buttons."])
    )


@router.message(SellerBotCreateStates.panel_username)
async def sellerbot_create_panel_username(message: Message, state: FSMContext) -> None:
    username = (message.text or "").strip()
    if not username or username.startswith("/"):
        await message.answer(
            "\n".join([title("Add Seller Bot"), "Send a panel username, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_panel_username=username[:128])
    await state.set_state(SellerBotCreateStates.panel_password)
    await message.answer(
        "\n".join(
            [
                title("Add Seller Bot"),
                "Send the Marzban admin password for this new panel.",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.panel_password)
async def sellerbot_create_panel_password(message: Message, state: FSMContext) -> None:
    password = (message.text or "").strip()
    if not password or password.startswith("/"):
        await message.answer(
            "\n".join([title("Add Seller Bot"), "Send the panel password, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_panel_password=password)
    await state.set_state(SellerBotCreateStates.panel_admin)
    await message.answer(
        "\n".join(
            [
                title("Add Seller Bot"),
                "Send the Marzban admin username used for provisioning.",
                "",
                "Send - to use the panel login username.",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.panel_token)
async def sellerbot_create_panel_token(message: Message, state: FSMContext) -> None:
    token_value = (message.text or "").strip()
    if not token_value or token_value.startswith("/"):
        await message.answer(
            "\n".join([title("Add Seller Bot"), "Send the panel token, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_panel_token=token_value)
    await state.set_state(SellerBotCreateStates.panel_admin)
    await message.answer(
        "\n".join(
            [
                title("Add Seller Bot"),
                "Send the Marzban admin username used for provisioning.",
                "",
                "Send - to skip and use the default panel scope.",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.panel_admin)
async def sellerbot_create_panel_admin(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    if not raw_value or raw_value.startswith("/"):
        await message.answer(
            "\n".join(
                [
                    title("Add Seller Bot"),
                    "Type a Marzban admin username, or send - for default.",
                    "",
                    "Example: sina_reseller",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    panel_admin = None if raw_value == "-" else raw_value[:128]
    await state.update_data(sellerbot_panel_admin=panel_admin)
    await state.set_state(SellerBotCreateStates.volume)
    await message.answer(
        "\n".join([
            title("Add Seller Bot"),
            "Send the total GB limit for this seller bot.",
            "Use 0 to start with no sellable capacity.",
            "",
            "Example: 500",
        ]),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
    )


@router.message(SellerBotCreateStates.volume)
async def sellerbot_create_volume(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    volume_limit_gb = _parse_non_negative_int(raw_value)
    if volume_limit_gb is None:
        await message.answer(
            "\n".join(
                [
                    title("Add Seller Bot"),
                    "Volume must be 0 or a positive number in GB.",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="sellerbot_cancel"),
        )
        return
    await state.update_data(sellerbot_volume_limit_gb=volume_limit_gb)
    await state.set_state(SellerBotCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        _sellerbot_confirm_text(data),
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


@router.message(SellerBotVolumeEditStates.volume)
async def sellerbot_volume_edit_message(
    message: Message,
    state: FSMContext,
    reseller_service: ResellerService,
) -> None:
    data = await state.get_data()
    seller_bot_id = str(data.get("seller_volume_bot_id") or "")
    raw_value = (message.text or "").strip()
    volume_limit_gb = _parse_non_negative_int(raw_value)
    if volume_limit_gb is None:
        await message.answer(
            "\n".join(
                [
                    title("Set Seller Bot GB Limit"),
                    "Volume must be 0 or a positive number in GB.",
                ]
            )
        )
        return
    try:
        seller_bot = await reseller_service.set_seller_bot_volume(
            seller_bot_id=seller_bot_id,
            volume_limit_gb=volume_limit_gb,
            actor_telegram_id=message.from_user.id if message.from_user else None,
        )
    except ValueError:
        await state.clear()
        await message.answer("Seller bot not found.", reply_markup=master_section_menu("seller_bots"))
        return
    await state.clear()
    await message.answer(
        "\n".join(
            [
                title("Seller Bot Volume Updated"),
                f"Bot: {seller_bot.name}",
                f"Limit: {_seller_bot_volume_text(seller_bot)}",
            ]
        ),
        reply_markup=master_seller_bot_actions(seller_bot.id),
    )


@router.message(SellerBotVolumeAddStates.amount)
async def sellerbot_volume_add_amount(
    message: Message,
    state: FSMContext,
    reseller_service: ResellerService,
) -> None:
    added_gb = _parse_positive_int(message.text)
    if added_gb is None:
        await message.answer(
            "\n".join(
                [
                    title("Add Seller Bot GB"),
                    "Amount must be a positive number in GB.",
                ]
            )
        )
        return
    data = await state.get_data()
    seller_bot_id = str(data.get("seller_volume_bot_id") or "")
    seller_bot = await _find_seller_bot(reseller_service, seller_bot_id=seller_bot_id)
    if seller_bot is None:
        await state.clear()
        await message.answer("Seller bot not found.", reply_markup=master_section_menu("seller_bots"))
        return
    quota = await reseller_service.seller_bot_quota(seller_bot_id=seller_bot.id)
    new_limit = quota.limit_gb + added_gb
    new_remaining = quota.remaining_gb + added_gb
    await state.update_data(seller_volume_add_gb=added_gb)
    await state.set_state(SellerBotVolumeAddStates.confirm)
    await message.answer(
        "\n".join(
            [
                title("Confirm Seller Bot GB Add"),
                f"Bot: {seller_bot.name}",
                f"Current limit: {_quota_value_text(quota.limit_gb)}",
                f"Used: {quota.used_gb} GB",
                f"Reserved: {quota.reserved_gb} GB",
                f"Current remaining: {_quota_value_text(quota.remaining_gb)}",
                f"Added: {added_gb} GB",
                f"New limit: {_quota_value_text(new_limit)}",
                f"New remaining: {_quota_value_text(new_remaining)}",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="seller_volume_add_confirm",
            cancel_action="seller_volume_add_cancel",
        ),
    )


@router.message(SellerBotVolumeAddStates.confirm)
async def sellerbot_volume_add_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Seller Bot GB Add"), "Use Confirm or Cancel below the preview."])
    )


@router.message(SellerBotSearchStates.query)
async def sellerbot_search_query(
    message: Message,
    state: FSMContext,
    reseller_service: ResellerService,
) -> None:
    query = (message.text or "").strip()
    if not query or query.startswith("/"):
        await message.answer(
            "\n".join([title("Search Seller Bots"), "Send a search phrase, not a command."]),
            reply_markup=master_section_menu("seller_bots"),
        )
        return
    seller_bots = [
        seller_bot
        for seller_bot in await reseller_service.list_seller_bots()
        if _seller_bot_matches_query(seller_bot, query)
    ]
    await state.clear()
    if not seller_bots:
        await message.answer(
            "\n".join([title("Search Seller Bots"), "No matching seller bots found."]),
            reply_markup=seller_bot_list_menu(page=1, total_pages=1),
        )
        return
    page = paginate(seller_bots, page=1, per_page=10)
    labels = await _seller_bot_list_labels(reseller_service, list(page.items))
    await message.answer(
        _seller_bots_search_text(query, seller_bots),
        reply_markup=seller_bot_list_menu(
            page=page.page,
            total_pages=page.total_pages,
            seller_bots=list(page.items),
            labels=labels,
        ),
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


@router.message(ReportCustomStates.days)
async def report_custom_days(
    message: Message,
    reseller_service: ResellerService,
    state: FSMContext,
) -> None:
    days = _parse_bounded_days(message.text)
    if days is None:
        await message.answer(
            "\n".join([title("Custom Report"), "Send a number from 1 to 365."]),
            reply_markup=master_section_menu("reports"),
        )
        return
    report = await reseller_service.global_report(days=days)
    await state.clear()
    await message.answer(
        _format_report(f"Global Report - Last {days} Days", report),
        reply_markup=master_section_menu("reports"),
    )


@router.message(PanelTokenCreateStates.name)
async def panel_token_create_name(message: Message, state: FSMContext) -> None:
    panel_name = (message.text or "").strip()
    if not panel_name or panel_name.startswith("/"):
        await message.answer(
            "\n".join([title("Add Token Panel"), "Send a panel name, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_token_cancel"),
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
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_token_cancel"),
    )


@router.message(PanelTokenCreateStates.base_url)
async def panel_token_create_base_url(message: Message, state: FSMContext) -> None:
    base_url = (message.text or "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        await message.answer(
            "\n".join([title("Add Token Panel"), "Send a valid URL starting with http:// or https://."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_token_cancel"),
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
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_token_cancel"),
    )


@router.message(PanelTokenCreateStates.token)
async def panel_token_create_token(message: Message, state: FSMContext) -> None:
    token_value = (message.text or "").strip()
    if not token_value or token_value.startswith("/"):
        await message.answer(
            "\n".join([title("Add Token Panel"), "Send the panel token, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_token_cancel"),
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
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_cancel"),
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
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_cancel"),
    )


@router.message(PanelPasswordCreateStates.base_url)
async def panel_password_create_base_url(message: Message, state: FSMContext) -> None:
    base_url = (message.text or "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        await message.answer(
            "\n".join([title("Add Login Panel"), "Send a valid URL starting with http:// or https://."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_cancel"),
        )
        return
    await state.update_data(panel_password_base_url=base_url)
    await state.set_state(PanelPasswordCreateStates.username)
    await message.answer(
        "\n".join([title("Add Login Panel"), "Send the Marzban admin username."]),
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_cancel"),
    )


@router.message(PanelPasswordCreateStates.username)
async def panel_password_create_username(message: Message, state: FSMContext) -> None:
    username = (message.text or "").strip()
    if not username or username.startswith("/"):
        await message.answer(
            "\n".join([title("Add Login Panel"), "Send a username, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_cancel"),
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
        reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_cancel"),
    )


@router.message(PanelPasswordCreateStates.password)
async def panel_password_create_password(message: Message, state: FSMContext) -> None:
    password = (message.text or "").strip()
    if not password or password.startswith("/"):
        await message.answer(
            "\n".join([title("Add Login Panel"), "Send the panel password, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_cancel"),
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


@router.message(PanelPasswordEditStates.password)
async def panel_password_edit_password(message: Message, state: FSMContext) -> None:
    password = (message.text or "").strip()
    if not password or password.startswith("/"):
        await message.answer(
            "\n".join([title("Change Panel Password"), "Send the new password, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_password_edit_cancel"),
        )
        return
    await state.update_data(panel_password_edit_value=password)
    await state.set_state(PanelPasswordEditStates.confirm)
    await message.answer(
        "\n".join([title("Confirm Password Change"), "Password: hidden"]),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="panel_password_edit_apply",
            cancel_action="panel_password_edit_cancel",
        ),
    )


@router.message(PanelPasswordEditStates.confirm)
async def panel_password_edit_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Password Change"), "Use Confirm or Cancel below the preview."])
    )


@router.message(PanelTokenEditStates.token)
async def panel_token_edit_token(message: Message, state: FSMContext) -> None:
    token_value = (message.text or "").strip()
    if not token_value or token_value.startswith("/"):
        await message.answer(
            "\n".join([title("Change Panel Token"), "Send the new token, not a command."]),
            reply_markup=cancel_only_keyboard(scope="m", cancel_action="panel_token_edit_cancel"),
        )
        return
    await state.update_data(panel_token_edit_value=token_value)
    await state.set_state(PanelTokenEditStates.confirm)
    await message.answer(
        "\n".join([title("Confirm Token Change"), "Token: hidden"]),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="panel_token_edit_apply",
            cancel_action="panel_token_edit_cancel",
        ),
    )


@router.message(PanelTokenEditStates.confirm)
async def panel_token_edit_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Token Change"), "Use Confirm or Cancel below the preview."])
    )


@router.message(PanelAssignmentCreateStates.reseller)
async def panel_assignment_waiting_for_reseller(message: Message) -> None:
    await message.answer(
        "\n".join([title("Assign Panel"), "Select a reseller using the buttons."])
    )


@router.message(PanelAssignmentCreateStates.panel)
async def panel_assignment_waiting_for_panel(message: Message) -> None:
    await message.answer(
        "\n".join([title("Assign Panel"), "Select a panel using the buttons."])
    )


@router.message(PanelAssignmentCreateStates.admin_username)
async def panel_assignment_admin_username(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    if not raw_value or raw_value.startswith("/"):
        await message.answer(
            "\n".join([title("Assign Panel"), "Send a username or - to skip."]),
            reply_markup=master_section_menu("panels"),
        )
        return
    admin_username = None if raw_value == "-" else raw_value[:128]
    await state.update_data(panel_assign_admin_username=admin_username)
    await state.set_state(PanelAssignmentCreateStates.priority)
    await message.answer(
        "\n".join(
            [
                title("Assign Panel"),
                "Send the routing priority.",
                "",
                "Lower priority is tried first. Example: 100",
            ]
        ),
        reply_markup=master_section_menu("panels"),
    )


@router.message(PanelAssignmentCreateStates.priority)
async def panel_assignment_priority(message: Message, state: FSMContext) -> None:
    priority = _parse_positive_int(message.text)
    if priority is None:
        await message.answer(
            "\n".join([title("Assign Panel"), "Send a valid priority number. Example: 100"]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_assign_priority=priority)
    await state.set_state(PanelAssignmentCreateStates.weight)
    await message.answer(
        "\n".join(
            [
                title("Assign Panel"),
                "Send the routing weight.",
                "",
                "Higher weight gets more traffic among equal priority panels. Example: 1",
            ]
        ),
        reply_markup=master_section_menu("panels"),
    )


@router.message(PanelAssignmentCreateStates.weight)
async def panel_assignment_weight(message: Message, state: FSMContext) -> None:
    weight = _parse_positive_int(message.text)
    if weight is None:
        await message.answer(
            "\n".join([title("Assign Panel"), "Send a valid weight number. Example: 1"]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_assign_weight=weight)
    await state.set_state(PanelAssignmentCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Panel Assignment"),
                f"Reseller Telegram: {data.get('panel_assign_reseller_telegram_id')}",
                f"Panel ID: {data.get('panel_assign_panel_id')}",
                f"Marzban admin: {data.get('panel_assign_admin_username') or '-'}",
                f"Priority: {data.get('panel_assign_priority')}",
                f"Weight: {data.get('panel_assign_weight')}",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="panel_assign_create",
            cancel_action="panel_assign_cancel",
        ),
    )


@router.message(PanelAssignmentCreateStates.confirm)
async def panel_assignment_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Panel Assignment"), "Use Confirm or Cancel below the preview."])
    )


@router.message(PanelAssignmentRoutingStates.priority)
async def panel_assignment_routing_priority(message: Message, state: FSMContext) -> None:
    priority = _parse_positive_int(message.text)
    if priority is None:
        await message.answer(
            "\n".join([title("Edit Panel Routing"), "Send a valid priority number. Example: 100"]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_routing_priority=priority)
    await state.set_state(PanelAssignmentRoutingStates.weight)
    await message.answer(
        "\n".join([title("Edit Panel Routing"), "Send the new weight. Example: 1"]),
        reply_markup=master_section_menu("panels"),
    )


@router.message(PanelAssignmentRoutingStates.weight)
async def panel_assignment_routing_weight(message: Message, state: FSMContext) -> None:
    weight = _parse_positive_int(message.text)
    if weight is None:
        await message.answer(
            "\n".join([title("Edit Panel Routing"), "Send a valid weight number. Example: 1"]),
            reply_markup=master_section_menu("panels"),
        )
        return
    await state.update_data(panel_routing_weight=weight)
    await state.set_state(PanelAssignmentRoutingStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Routing"),
                f"Assignment ID: {data.get('panel_routing_assignment_id')}",
                f"Priority: {data.get('panel_routing_priority')}",
                f"Weight: {data.get('panel_routing_weight')}",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="panel_routing_update",
            cancel_action="panel_routing_cancel",
        ),
    )


@router.message(PanelAssignmentRoutingStates.confirm)
async def panel_assignment_routing_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Routing"), "Use Confirm or Cancel below the preview."])
    )


@router.message(ForcedJoinCreateStates.chat_id)
async def forced_join_create_chat_id(message: Message, state: FSMContext) -> None:
    chat_id = (message.text or "").strip()
    if not chat_id or chat_id.startswith("/"):
        await message.answer(
            "\n".join([title("Add Forced Join"), "Send a chat ID or @username, not a command."]),
            reply_markup=forced_join_menu(),
        )
        return
    await state.update_data(forced_join_chat_id=chat_id[:128])
    await state.set_state(ForcedJoinCreateStates.title)
    await message.answer(
        "\n".join([title("Add Forced Join"), "Send the display title for users, or - to use the ID."]),
        reply_markup=forced_join_menu(),
    )


@router.message(ForcedJoinCreateStates.title)
async def forced_join_create_title(message: Message, state: FSMContext) -> None:
    raw_title = (message.text or "").strip()
    if not raw_title or raw_title.startswith("/"):
        await message.answer(
            "\n".join([title("Add Forced Join"), "Send a title or - to skip."]),
            reply_markup=forced_join_menu(),
        )
        return
    chat_title = None if raw_title == "-" else raw_title[:128]
    await state.update_data(forced_join_title=chat_title)
    await state.set_state(ForcedJoinCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("Confirm Forced Join"),
                f"Chat: {data.get('forced_join_chat_id')}",
                f"Title: {data.get('forced_join_title') or '-'}",
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="forced_join_create",
            cancel_action="forced_join_cancel",
        ),
    )


@router.message(ForcedJoinCreateStates.confirm)
async def forced_join_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Forced Join"), "Use Confirm or Cancel below the preview."])
    )


@router.message(ForcedJoinRemoveStates.chat_id)
async def forced_join_remove_chat_id(message: Message, state: FSMContext) -> None:
    chat_id = (message.text or "").strip()
    if not chat_id or chat_id.startswith("/"):
        await message.answer(
            "\n".join([title("Remove Forced Join"), "Send a chat ID or @username, not a command."]),
            reply_markup=forced_join_menu(),
        )
        return
    await state.update_data(forced_join_remove_chat_id=chat_id[:128])
    await state.set_state(ForcedJoinRemoveStates.confirm)
    await message.answer(
        "\n".join([title("Confirm Remove Forced Join"), f"Chat: {chat_id[:128]}"]),
        reply_markup=confirm_keyboard(
            scope="m",
            confirm_action="forced_join_remove_apply",
            cancel_action="forced_join_remove_cancel",
        ),
    )


@router.message(ForcedJoinRemoveStates.confirm)
async def forced_join_remove_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("Confirm Remove Forced Join"), "Use Confirm or Cancel below the preview."])
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


@router.message(Command("create_seller_bot"))
async def create_seller_bot(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = _parse_args(command.args)
    if len(args) not in {7, 8, 9} or not args[0].isdigit():
        await message.answer(
            "Usage: /create_seller_bot <admin_telegram_id> <seller_bot_name> "
            "<seller_bot_token> <panel_name> <panel_base_url> <marzban_username> "
            "<marzban_password> [marzban_admin_username] [volume_limit_gb]"
        )
        return
    volume_limit_gb = 0
    if len(args) == 9:
        volume_limit_gb = _parse_non_negative_int(args[8])
        if volume_limit_gb is None:
            await message.answer("volume_limit_gb must be 0 or a positive whole number.")
            return
    try:
        result = await reseller_service.provision_seller_bot_with_password_panel(
            reseller_telegram_id=int(args[0]),
            reseller_display_name=f"Admin {args[0]}",
            bot_name=args[1].strip(),
            bot_token=args[2].strip(),
            panel_name=args[3].strip(),
            panel_base_url=args[4].strip(),
            panel_username=args[5].strip(),
            panel_password=args[6].strip(),
            marzban_admin_username=args[7].strip() if len(args) >= 8 else None,
            volume_limit_gb=volume_limit_gb,
            actor_telegram_id=message.from_user.id if message.from_user else None,
        )
    except ValueError as exc:
        if str(exc) == "panel_credentials_required":
            await message.answer("Marzban username and password are required.")
            return
        raise

    await message.answer(
        "\n".join(
            [
                "Seller bot created.",
                f"Admin Telegram ID: {result.reseller.telegram_user_id}",
                f"Admin record: {'existing' if result.reseller_existed else 'created'}",
                f"Seller Bot ID: {result.seller_bot.id}",
                f"Seller Bot Name: {result.seller_bot.name}",
                f"Panel ID: {result.panel.id}",
                f"Panel Name: {result.panel.name}",
                f"Marzban admin: {result.assignment.marzban_admin_username or '-'}",
                f"Volume limit GB: {result.seller_bot.volume_limit_gb}",
            ]
        )
    )


@router.message(Command("add_external_template"))
async def add_external_template(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = _parse_args(command.args)
    if len(args) < 4:
        await message.answer(
            "Usage: /add_external_template <key> <name> <repo_url> <ref> "
            "[local_path] [license] [runtime_adapter]"
        )
        return
    try:
        template = await reseller_service.register_external_bot_template(
            key=args[0],
            name=args[1],
            repo_url=args[2],
            ref=args[3],
            local_path=args[4] if len(args) >= 5 else None,
            license_name=args[5] if len(args) >= 6 else None,
            runtime_adapter=args[6] if len(args) >= 7 else "manual",
            actor_telegram_id=message.from_user.id if message.from_user else None,
        )
    except ValueError as exc:
        if str(exc) == "external_template_exists":
            await message.answer("External template already exists.")
            return
        if str(exc) == "invalid_template_key":
            await message.answer("Template key must not be empty or contain spaces.")
            return
        raise
    await message.answer(_external_template_text(template), reply_markup=external_template_actions(template.id))


@router.message(Command("list_external_templates"))
async def list_external_templates(message: Message, reseller_service: ResellerService) -> None:
    await message.answer(
        await _external_bots_text(reseller_service),
        reply_markup=master_section_menu("external_bots"),
    )


@router.message(Command("sync_external_template"))
async def sync_external_template(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    template_id_or_key = (command.args or "").strip()
    if not template_id_or_key:
        await message.answer("Usage: /sync_external_template <template_id_or_key>")
        return
    try:
        result = await reseller_service.sync_external_bot_template(
            template_id_or_key=template_id_or_key,
            actor_telegram_id=message.from_user.id if message.from_user else None,
        )
    except ValueError:
        await message.answer("External template not found.")
        return
    await message.answer(
        "\n".join(
            [
                "External template sync complete." if result.ok else "External template sync failed.",
                f"Name: {result.template.name}",
                f"Key: {result.template.key}",
                f"Result: {result.message}",
            ]
        ),
        reply_markup=external_template_actions(result.template.id),
    )


@router.message(Command("add_external_seller_bot"))
async def add_external_seller_bot(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = _parse_args(command.args)
    if len(args) != 4 or not args[0].isdigit():
        await message.answer(
            "Usage: /add_external_seller_bot <reseller_telegram_id> "
            '<bot_name> <bot_token> <template_id_or_key>'
        )
        return
    try:
        seller_bot = await reseller_service.register_external_seller_bot(
            reseller_telegram_id=int(args[0]),
            bot_name=args[1].strip(),
            bot_token=args[2].strip(),
            template_id_or_key=args[3].strip(),
            actor_telegram_id=message.from_user.id if message.from_user else None,
        )
    except ValueError as exc:
        if str(exc) == "reseller_not_found":
            await message.answer("Reseller not found. Add reseller first.")
            return
        if str(exc) == "external_template_not_found":
            await message.answer("External template not found or disabled.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "External seller bot registered.",
                f"ID: {seller_bot.id}",
                f"Name: {seller_bot.name}",
                f"Runtime: {seller_bot.runtime_type}",
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

    try:
        panel = await reseller_service.register_marzban_panel(
            name=args[0].strip(),
            base_url=args[1].strip(),
            token=args[2].strip(),
        )
    except ValueError as exc:
        await message.answer(_panel_error_message(exc))
        return
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

    try:
        panel = await reseller_service.register_marzban_panel(
            name=args[0].strip(),
            base_url=args[1].strip(),
            username=args[2].strip(),
            password=args[3].strip(),
        )
    except ValueError as exc:
        await message.answer(_panel_error_message(exc))
        return
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
            priority=100,
            weight=1,
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
            title("پنل مدیریت"),
            "از منوی زیر یکی را انتخاب کنید.",
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


def _paginate_resellers(resellers, *, page: int):
    return paginate(list(resellers), page=page, per_page=5)


def _resellers_page_text(page) -> str:
    rows = [
        f"- {reseller.display_name} | {status_label(reseller.status)} | tg={reseller.telegram_user_id}"
        for reseller in page.items
    ]
    rows.extend(
        [
            "",
            "Use Add Seller Bot to onboard a new owner and bot.",
            f"Page: {page.page}/{page.total_pages}",
            f"Total: {page.total_items}",
        ]
    )
    return "\n".join([title("Resellers"), section("Resellers", rows)])


async def _find_reseller_by_telegram_id(reseller_service: ResellerService, *, telegram_id: int):
    resellers = await reseller_service.list_resellers()
    return next((reseller for reseller in resellers if reseller.telegram_user_id == telegram_id), None)


async def _find_reseller_by_id(reseller_service: ResellerService, *, reseller_id: str):
    resellers = await reseller_service.list_resellers()
    return next((reseller for reseller in resellers if reseller.id == reseller_id), None)


async def _find_seller_bot(reseller_service: ResellerService, *, seller_bot_id: str):
    seller_bots = await reseller_service.list_seller_bots()
    return next((seller_bot for seller_bot in seller_bots if seller_bot.id == seller_bot_id), None)


async def _reseller_detail_text(reseller_service: ResellerService, reseller) -> str:
    seller_bots = [item for item in await reseller_service.list_seller_bots() if item.reseller_id == reseller.id]
    plans = [item for item in await reseller_service.list_plans() if item.reseller_id == reseller.id]
    assignments = await reseller_service.list_panel_assignments_for_reseller(reseller_id=reseller.id)
    return "\n".join(
        [
            title("Reseller Detail"),
            f"Name: {reseller.display_name}",
            f"Telegram: {reseller.telegram_user_id}",
            f"Status: {status_label(reseller.status)}",
            f"Wallet: {reseller.wallet_balance:,.0f}",
            f"Seller bots: {len(seller_bots)}",
            f"Plans: {len(plans)}",
            f"Panel assignments: {len(assignments)}",
            f"ID: {reseller.id}",
        ]
    )


async def _reseller_seller_bots_text(reseller_service: ResellerService, reseller) -> str:
    seller_bots = [item for item in await reseller_service.list_seller_bots() if item.reseller_id == reseller.id]
    rows = [
        f"- {item.name} | {status_label(item.status)} | id={short_id(item.id)} | container={item.container_name or '-'}"
        for item in seller_bots[:20]
    ]
    rows.extend(["", f"Reseller: {reseller.display_name}"])
    return "\n".join([title("Reseller Seller Bots"), section("Bots", rows)])


async def _reseller_plans_text(reseller_service: ResellerService, reseller) -> str:
    plans = [item for item in await reseller_service.list_plans() if item.reseller_id == reseller.id]
    rows = []
    for plan in plans[:20]:
        traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
        rows.append(f"- {plan.name} | {plan.price:,.0f} | {plan.duration_days}d | {traffic} | id={short_id(plan.id)}")
    rows.extend(["", f"Reseller: {reseller.display_name}"])
    return "\n".join([title("Reseller Plans"), section("Plans", rows)])


async def _reseller_panels_text(reseller_service: ResellerService, reseller) -> str:
    assignments = await reseller_service.list_panel_assignments_for_reseller(reseller_id=reseller.id)
    rows = [
        (
            f"- {item.panel.name} | priority={item.assignment.priority} | weight={item.assignment.weight} | "
            f"admin={item.assignment.marzban_admin_username or '-'} | id={short_id(item.assignment.id)}"
        )
        for item in assignments[:20]
    ]
    rows.extend(["", f"Reseller: {reseller.display_name}"])
    return "\n".join([title("Panel Assignments"), section("Assignments", rows)])


def _reseller_seller_bots_keyboard(seller_bots) -> InlineKeyboardMarkup:
    rows = [
        [(seller_bot.name[:32], build_callback("m", "seller_select", seller_bot.id))]
        for seller_bot in seller_bots[:10]
    ]
    rows.append([("Back", build_callback("m", "resellers")), ("Home", build_callback("m", "home"))])
    return inline_keyboard(rows)


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


def _external_template_select_keyboard(templates):
    rows = [[(template.name, f"m:sellerbot_template:{template.key}")] for template in templates]
    rows.append([("Cancel", "m:sellerbot_cancel"), ("Home", "m:home")])
    return inline_keyboard(rows)


def _panel_select_keyboard(panels, *, action_name: str, cancel_action: str):
    rows = [
        [(panel.name, f"m:{action_name}:{panel.id}")]
        for panel in panels
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
    rows.extend(
        [
            "",
            "Use Add Seller Bot to onboard a new bot with a new panel.",
            "Use Assign Panel only for advanced multi-panel routing.",
        ]
    )
    return "\n".join([title("Panels"), section("Registered panels", rows)])


def _panel_assignment_detail_text(assignment) -> str:
    return "\n".join(
        [
            title("Panel Assigned"),
            f"Assignment ID: {assignment.id}",
            f"Reseller ID: {assignment.reseller_id}",
            f"Panel ID: {assignment.panel_id}",
            f"Marzban admin: {assignment.marzban_admin_username or '-'}",
            f"Priority: {assignment.priority}",
            f"Weight: {assignment.weight}",
            f"Status: {status_label('active' if assignment.is_active else 'disabled')}",
        ]
    )


def _panel_assignment_actions(assignment_id: str, reseller_telegram_id: int | None = None):
    rows = [
        [("Edit Priority/Weight", f"m:panel_routing_edit:{assignment_id}")],
    ]
    if reseller_telegram_id is not None:
        rows.append([("Back", f"m:reseller_panels:{reseller_telegram_id}"), ("Home", "m:home")])
    else:
        rows.append([("Panels", "m:panels"), ("Home", "m:home")])
    return inline_keyboard(rows)


def _panel_detail_text(detail) -> str:
    panel = detail.panel
    return "\n".join(
        [
            title("Panel Detail"),
            f"Name: {panel.name}",
            f"Base URL: {panel.base_url}",
            f"Auth type: {detail.auth_type}",
            f"Status: {status_label('active' if panel.is_active else 'disabled')}",
            f"Assignments: {detail.assignment_count}",
            f"ID: {panel.id}",
        ]
    )


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


async def _seller_bot_list_labels(
    reseller_service: ResellerService,
    seller_bots: list,
) -> dict[str, str]:
    labels: dict[str, str] = {}
    for seller_bot in seller_bots:
        quota = await reseller_service.seller_bot_quota(seller_bot_id=seller_bot.id)
        labels[seller_bot.id] = (
            f"{seller_bot.name[:16]} | {seller_bot.status[:8]} | {quota.used_gb}/{quota.limit_gb}GB"
        )
    return labels


async def _seller_bots_page_text(reseller_service: ResellerService, page) -> str:
    rows = []
    for seller_bot in page.items:
        quota = await reseller_service.seller_bot_quota(seller_bot_id=seller_bot.id)
        rows.append(
            f"- {seller_bot.name} | {status_label(seller_bot.status)} | "
            f"{quota.used_gb}/{quota.limit_gb} GB | id={short_id(seller_bot.id)}"
        )
    if not rows:
        rows.append("No seller bots yet. Use Add Seller Bot to create one.")
    rows.extend(["", f"Page: {page.page}/{page.total_pages}", f"Total: {page.total_items}"])
    return "\n".join([title("Seller Bots"), section("Bots", rows)])


def _seller_bot_volume_text(seller_bot) -> str:
    volume_limit_gb = getattr(seller_bot, "volume_limit_gb", None) or 0
    return f"{volume_limit_gb} GB"


def _quota_value_text(value: int | None) -> str:
    return f"{value or 0} GB"


async def _seller_bot_card_text(reseller_service: ResellerService, seller_bot) -> str:
    quota = await reseller_service.seller_bot_quota(seller_bot_id=seller_bot.id)
    return "\n".join(
        [
            title("Seller Bot"),
            f"Name: {seller_bot.name}",
            f"ID: {seller_bot.id}",
            f"Runtime: {getattr(seller_bot, 'runtime_type', 'native')}",
            f"Status: {status_label(seller_bot.status)}",
            f"Volume limit: {_seller_bot_volume_text(seller_bot)}",
            f"Used: {quota.used_gb} GB",
            f"Reserved: {quota.reserved_gb} GB",
            f"Remaining: {_quota_value_text(quota.remaining_gb)}",
            f"Container: {seller_bot.container_name or '-'}",
        ]
    )


def _seller_bot_admins_text(seller_bot, reseller) -> str:
    return "\n".join(
        [
            title("Bot Admins"),
            f"Bot: {seller_bot.name}",
            "",
            "Owner/admin:",
            f"- {reseller.display_name} | Telegram: {reseller.telegram_user_id}",
            "",
            "Platform super user is also co-admin on this bot.",
        ]
    )


def _seller_bot_matches_query(seller_bot, query: str) -> bool:
    normalized_query = query.strip().lower()
    values = [
        seller_bot.id,
        short_id(seller_bot.id),
        seller_bot.name,
        seller_bot.status,
        getattr(seller_bot, "runtime_type", ""),
        seller_bot.container_name or "",
        seller_bot.container_id or "",
    ]
    return any(normalized_query in str(value).lower() for value in values)


def _seller_bots_search_text(query: str, seller_bots) -> str:
    rows = [
        f"- {seller_bot.name} | {status_label(seller_bot.status)} | id={short_id(seller_bot.id)}"
        for seller_bot in seller_bots[:10]
    ]
    rows.extend(["", f"Matches: {len(seller_bots)}"])
    return "\n".join([title("Search Seller Bots"), f"Query: {query}", "", section("Matches", rows)])


def _sellerbot_confirm_text(data: dict, *, error: str | None = None) -> str:
    panel_auth = data.get("sellerbot_panel_auth") or "-"
    lines = [
        title("تأیید ربات جدید"),
        f"نوع: {data.get('sellerbot_ui_profile') or 'platform'}",
        f"آیدی مالک: {data.get('sellerbot_owner_telegram_id')}",
        f"یوزرنیم: @{data.get('sellerbot_owner_username')}",
        f"نام مالک: {data.get('sellerbot_owner_display_name')}",
        f"Bot name: {data.get('sellerbot_name')}",
        f"Panel name: {data.get('sellerbot_panel_name')}",
        f"Panel URL: {data.get('sellerbot_panel_base_url')}",
        f"Panel auth: {panel_auth}",
        f"Marzban admin: {data.get('sellerbot_panel_admin') or '-'}",
        f"Stock: {data.get('sellerbot_volume_limit_gb') or 0} GB",
        "Bot token: hidden",
        "Panel secret: hidden",
    ]
    if error:
        lines.extend(["", f"Could not create seller bot: {error}"])
    return "\n".join(lines)


async def _external_bots_text(reseller_service: ResellerService) -> str:
    templates = await reseller_service.list_external_bot_templates()
    rows = [
        (
            f"- {template.name} | key={template.key} | adapter={template.runtime_adapter} | "
            f"commit={short_id(template.last_synced_commit) if template.last_synced_commit else '-'}"
        )
        for template in templates[:20]
    ]
    if not rows:
        rows.append("No external bot templates registered yet.")
    rows.extend(["", "Use templates only after checking license and runtime requirements."])
    return "\n".join([title("External Bot Templates"), section("Templates", rows)])


def _external_template_text(template) -> str:
    return "\n".join(
        [
            title("External Bot Template"),
            f"Name: {template.name}",
            f"Key: {template.key}",
            f"Repo: {template.repo_url}",
            f"Ref: {template.ref}",
            f"Path: {template.local_path or '-'}",
            f"License: {template.license_name or '-'}",
            f"Adapter: {template.runtime_adapter}",
            f"Commit: {template.last_synced_commit or '-'}",
            f"Last error: {template.last_sync_error or '-'}",
            f"ID: {template.id}",
        ]
    )


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


def _plan_card_text(plan) -> str:
    traffic = "Unlimited" if plan.data_limit_gb is None else f"{plan.data_limit_gb} GB"
    scope = "Global" if plan.reseller_id is None else f"Seller {short_id(plan.reseller_id)}"
    return "\n".join(
        [
            title("Plan Action"),
            f"Name: {plan.name}",
            f"Scope: {scope}",
            f"Price: {plan.price:,.0f}",
            f"Duration: {plan.duration_days} days",
            f"Traffic: {traffic}",
            f"Status: {status_label('active' if plan.is_active else 'disabled')}",
            f"ID: {plan.id}",
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


def _discount_card_text(discount) -> str:
    max_uses = "Unlimited" if discount.max_uses is None else str(discount.max_uses)
    scope = "Global" if discount.reseller_id is None else f"Seller {short_id(discount.reseller_id)}"
    return "\n".join(
        [
            title("Discount Action"),
            f"Code: {discount.code}",
            f"Scope: {scope}",
            f"Type: {discount.discount_type}",
            f"Amount: {discount.amount:g}",
            f"Uses: {discount.used_count}/{max_uses}",
            f"Status: {status_label('active' if discount.is_active else 'disabled')}",
            f"ID: {discount.id}",
        ]
    )


async def _broadcast_history_text(reseller_service: ResellerService) -> str:
    broadcasts = await reseller_service.list_global_broadcasts(limit=10)
    rows = [
        (
            f"- {item.title} | {status_label(item.status)} | "
            f"{item.sent_count}/{item.target_count} | id={short_id(item.id)}"
        )
        for item in broadcasts
    ]
    rows.extend(["", "Create drafts, review them, then send with confirmation."])
    return "\n".join([title("Broadcasts"), section("Recent global broadcasts", rows)])


def _broadcast_card_text(broadcast) -> str:
    return "\n".join(
        [
            title("Broadcast Action"),
            f"Title: {broadcast.title}",
            f"Status: {status_label(broadcast.status)}",
            f"Targets: {broadcast.sent_count}/{broadcast.target_count}",
            f"ID: {broadcast.id}",
        ]
    )


def _broadcast_detail_text(broadcast) -> str:
    body = " ".join((broadcast.body or "").split())
    if len(body) > 900:
        body = f"{body[:900]}..."
    return "\n".join(
        [
            title("Broadcast Detail"),
            f"ID: {broadcast.id}",
            f"Title: {broadcast.title}",
            f"Status: {status_label(broadcast.status)}",
            f"Targets: {broadcast.sent_count}/{broadcast.target_count}",
            f"Created: {broadcast.created_at:%Y-%m-%d %H:%M}",
            f"Sent: {broadcast.sent_at:%Y-%m-%d %H:%M}" if broadcast.sent_at else "Sent: -",
            "",
            body,
        ]
    )


def _settings_text() -> str:
    return "\n".join(
        [
            title("Settings"),
            "Choose the setting group to view or change.",
            "",
            "- Forced join controls required channels/groups.",
            "- Rate limits are configured by environment.",
            "- Trial and payment settings show the current operating mode.",
        ]
    )


def _settings_detail_text(action: str) -> str:
    details = {
        "settings_rate_limits": [
            title("Rate Limits"),
            "Bot action limits are enforced per user and command.",
            "Runtime setting: BOT_RATE_LIMIT_PER_MINUTE.",
        ],
        "settings_trial": [
            title("Trial Settings"),
            "Trial accounts use anti-abuse checks per buyer/reseller.",
            "Plan limits are controlled by the seller service configuration.",
        ],
        "settings_payments": [
            title("Payment Instructions"),
            "Card-to-card is the active adapter.",
            "Gateway adapters can be added without changing buyer flows.",
        ],
    }
    return "\n".join(details.get(action, [title("Settings"), "Unknown setting group."]))


async def _system_text(reseller_service: ResellerService) -> str:
    resellers = await reseller_service.list_resellers()
    seller_bots = await reseller_service.list_seller_bots()
    panels = await reseller_service.list_marzban_panels()
    return "\n".join(
        [
            title("System"),
            f"Health: {status_label('active')}",
            f"Resellers: {len(resellers)}",
            f"Seller bots: {len(seller_bots)}",
            f"Panels: {len(panels)}",
            "",
            "Use the buttons below for version, backup, audit, and error checks.",
        ]
    )


def _system_detail_text(action: str) -> str:
    details = {
        "system_health": [
            title("Healthcheck"),
            f"Master bot: {status_label('running')}",
            "Database: available through active service queries.",
        ],
        "system_version": [
            title("Deploy Version"),
            "Version is tracked by the deployed Git commit on server-04.",
            "Use CI/CD logs or SSH deploy output for the exact hash.",
        ],
        "system_backup": [
            title("Backup Timer"),
            "Postgres backup is configured during deploy on server-04.",
            "Timer status is available from the host with systemctl.",
        ],
        "system_errors": [
            title("Recent Errors"),
            "Runtime errors are visible from Docker logs and seller bot health screens.",
            "No secrets are shown in this screen.",
        ],
    }
    return "\n".join(details.get(action, [title("System"), "Unknown system screen."]))


async def _recent_audit_text(reseller_service: ResellerService) -> str:
    logs = await reseller_service.recent_audit_logs(limit=10)
    rows = [
        (
            f"- {item.created_at:%m-%d %H:%M} | {item.action} | "
            f"actor={item.actor_telegram_id or '-'} | target={short_id(item.target_id)}"
        )
        for item in logs
    ]
    return "\n".join([title("Recent Audit Logs"), section("Audit", rows)])


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
        "guide_add_external_template": (
            "Add External Template",
            "Register a GitHub seller bot as a managed template. This does not run it yet.",
            [
                '/add_external_template marzbot-free "Marzbot Free" '
                "https://github.com/govfvck/Marzbot-free main "
                "external/seller-bots/marzbot-free AGPL-3.0 manual"
            ],
        ),
        "guide_add_external_seller_bot": (
            "Add External Seller Bot",
            "Create a seller bot record that points to an external template.",
            [
                '/add_external_seller_bot <reseller_telegram_id> "Bot Name" '
                "<bot_token> <template_key>"
            ],
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
    if "external" in action:
        return master_section_menu("external_bots")
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
    if len(args) not in {4, 5}:
        await message.answer(
            "Usage: /add_global_plan <name> <price> <duration_days> <data_limit_gb|unlimited> [purchase|renewal|extra_volume|trial]"
        )
        return
    parsed = _parse_plan_args(args[1:4])
    if parsed is None:
        await message.answer("Price, duration, and data limit must be valid numbers. Use unlimited for no data limit.")
        return
    purpose = _parse_plan_purpose(args[4] if len(args) == 5 else None)
    if purpose is None:
        await message.answer("Plan purpose must be purchase, renewal, extra_volume, or trial.")
        return
    price, duration_days, data_limit_gb = parsed
    plan = await reseller_service.create_global_plan(
        name=args[0].strip(),
        price=price,
        duration_days=duration_days,
        data_limit_gb=data_limit_gb,
        purpose=purpose,
    )
    await message.answer(f"Global plan created.\nID: {plan.id}\nName: {plan.name}")


@router.message(Command("add_reseller_plan"))
async def add_reseller_plan(
    message: Message,
    command: CommandObject,
    reseller_service: ResellerService,
) -> None:
    args = _parse_args(command.args)
    if len(args) not in {5, 6} or not args[0].isdigit():
        await message.answer(
            "Usage: /add_reseller_plan <reseller_telegram_id> <name> <price> <duration_days> <data_limit_gb|unlimited> [purchase|renewal|extra_volume|trial]"
        )
        return
    parsed = _parse_plan_args(args[2:5])
    if parsed is None:
        await message.answer("Price, duration, and data limit must be valid numbers. Use unlimited for no data limit.")
        return
    purpose = _parse_plan_purpose(args[5] if len(args) == 6 else None)
    if purpose is None:
        await message.answer("Plan purpose must be purchase, renewal, extra_volume, or trial.")
        return
    price, duration_days, data_limit_gb = parsed
    try:
        plan = await reseller_service.create_reseller_plan(
            reseller_telegram_id=int(args[0]),
            name=args[1].strip(),
            price=price,
            duration_days=duration_days,
            data_limit_gb=data_limit_gb,
            purpose=purpose,
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
        lines.append(
            f"- {plan.name} | {plan.purpose} | {owner} | {plan.price:,.0f} | {plan.duration_days} days | {traffic} | id={plan.id}"
        )
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


def _parse_plan_purpose(value: str | None) -> PlanPurpose | None:
    if value is None:
        return PlanPurpose.PURCHASE
    try:
        return PlanPurpose(value.strip().lower())
    except ValueError:
        return None


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


def _parse_non_negative_int(raw: str | None) -> int | None:
    try:
        value = int((raw or "").strip().replace(",", ""))
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def _parse_bounded_days(raw: str | None) -> int | None:
    days = _parse_positive_int(raw)
    if days is None or days > 365:
        return None
    return days


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
    text = f"{draft.broadcast.title}\n➖➖➖\n{draft.broadcast.body}"
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
