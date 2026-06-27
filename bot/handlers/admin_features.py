from __future__ import annotations

from math import ceil

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.admin_discounts import (
    admin_discount_delete_confirm_keyboard,
    admin_discount_detail_keyboard,
    admin_discount_edit_max_uses_keyboard,
    admin_discount_edit_valid_days_keyboard,
    admin_discounts_list_keyboard,
    discount_detail_text,
    discount_list_line,
)
from bot.commands import sync_bot_commands
from bot.context import AppContext
from bot.db import Repository
from bot.formatting import with_footer
from bot.handlers.admin import _edit_callback_message, require_admin
from bot.keyboards import admin_back_keyboard, admin_discount_max_uses_keyboard, admin_discount_valid_days_keyboard
from bot.forced_join import resolve_required_chat
from bot.states import DiscountCreate, DiscountEdit, ForcedJoinAdd, TicketReply

router = Router()

LEDGER_PER_PAGE = 8


async def _prompt_discount_max_uses(message: Message) -> None:
    await message.answer(
        "حداکثر تعداد استفاده را بفرستید یا «نامحدود» را بزنید.",
        reply_markup=admin_discount_max_uses_keyboard(),
    )


async def _prompt_discount_valid_days(message: Message) -> None:
    await message.answer(
        "مدت اعتبار به روز را بفرستید یا «نامحدود» را بزنید.",
        reply_markup=admin_discount_valid_days_keyboard(),
    )


async def _create_discount_from_state(message: Message, state: FSMContext, ctx: AppContext, *, valid_days: int) -> None:
    data = await state.get_data()
    async with ctx.database.session() as db:
        await Repository(db).create_discount_code(
            str(data["discount_code"]),
            int(data["discount_percent"]),
            max_uses=int(data["discount_max_uses"]),
            valid_days=valid_days,
        )
    await state.clear()
    await message.answer("کد تخفیف ایجاد شد.", reply_markup=admin_back_keyboard())


async def _render_discount_detail(target: CallbackQuery | Message, ctx: AppContext, code_id: int) -> bool:
    async with ctx.database.session() as db:
        code = await Repository(db).get_discount_code_by_id(code_id)
    if code is None:
        if isinstance(target, CallbackQuery):
            await target.answer("کد پیدا نشد.", show_alert=True)
        else:
            await target.answer("کد پیدا نشد.", reply_markup=admin_back_keyboard())
        return False
    text = with_footer(discount_detail_text(code))
    markup = admin_discount_detail_keyboard(code.id)
    if isinstance(target, CallbackQuery):
        await _edit_callback_message(target, text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)
    return True


async def _render_discounts_list(target: CallbackQuery | Message, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        codes = await Repository(db).list_discount_codes()
    lines = ["کدهای تخفیف", ""]
    if not codes:
        lines.append("کدی ثبت نشده است.")
    else:
        for code in codes[:20]:
            lines.append(f"• {discount_list_line(code)}")
    text = with_footer("\n".join(lines))
    markup = admin_discounts_list_keyboard(codes)
    if isinstance(target, CallbackQuery):
        await _edit_callback_message(target, text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.callback_query(F.data == "admin:settings")
async def admin_settings_menu(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="جوین اجباری", callback_data="admin:join")],
            [InlineKeyboardButton(text="تست رایگان", callback_data="admin:trial")],
            [InlineKeyboardButton(text="کدهای تخفیف", callback_data="admin:discounts")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:panel")],
        ]
    )
    await _edit_callback_message(callback, with_footer("تنظیمات پیشرفته"), reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "admin:sales")
async def admin_sales_report(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        report = await Repository(db).sales_report(days=30)
    text = "\n".join(
        [
            "گزارش فروش",
            "",
            f"تعداد اشتراک‌ها: {report.subscription_count}",
            f"درآمد اشتراک: {report.subscription_revenue:,} تومان",
            f"تعداد شارژ کیف پول: {report.wallet_charges}",
            f"مجموع شارژ: {report.wallet_charge_total:,} تومان",
        ]
    )
    await _edit_callback_message(callback, with_footer(text), reply_markup=admin_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:join")
async def admin_join_menu(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        chats = await Repository(db).list_required_chats()
    lines = ["کانال‌های جوین اجباری", ""]
    if not chats:
        lines.append("کانالی ثبت نشده است.")
    else:
        for chat in chats:
            lines.append(f"• {chat.title or chat.chat_id}")
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    rows = [[InlineKeyboardButton(text="➕ افزودن کانال", callback_data="admin:join:add")]]
    for chat in chats:
        rows.append([InlineKeyboardButton(text=f"حذف {chat.title or chat.chat_id}", callback_data=f"admin:join:del:{chat.chat_id}")])
    rows.append([InlineKeyboardButton(text="بازگشت", callback_data="admin:settings")])
    await _edit_callback_message(callback, with_footer("\n".join(lines)), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "admin:join:add")
async def admin_join_add_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(ForcedJoinAdd.ref)
    await _edit_callback_message(
        callback,
        with_footer("آیدی عددی، @username یا لینک کانال (t.me/...) را بفرستید."),
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(ForcedJoinAdd.ref)
async def admin_join_ref(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("ورودی خالی است.")
        return
    try:
        chat_id, title, invite_link = await resolve_required_chat(message.bot, raw)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    async with ctx.database.session() as db:
        await Repository(db).add_required_chat(chat_id, title, invite_link)
    await state.clear()
    notice = f"کانال «{title}» اضافه شد."
    try:
        await message.bot.get_chat_member(chat_id, message.from_user.id)
    except TelegramAPIError:
        notice += (
            "\n\n⚠️ ربات الان نمی‌تواند عضویت کاربران را بررسی کند."
            "\nربات را ادمین کانال کن (بدون نیاز به همه دسترسی‌ها)."
        )
    await message.answer(notice, reply_markup=admin_back_keyboard())


@router.callback_query(F.data.startswith("admin:join:del:"))
async def admin_join_delete(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    chat_id = int(callback.data.rsplit(":", 1)[-1])
    async with ctx.database.session() as db:
        await Repository(db).remove_required_chat(chat_id)
    await admin_join_menu(callback, ctx)


@router.callback_query(F.data == "admin:trial")
async def admin_trial_settings(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        enabled = await repository.get_trial_enabled()
        traffic_mb = await repository.get_trial_traffic_mb()
        days = await repository.get_trial_days()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"وضعیت: {'فعال' if enabled else 'غیرفعال'}", callback_data="admin:trial:toggle")],
            [InlineKeyboardButton(text=f"حجم: {traffic_mb} MB", callback_data="admin:trial:gb")],
            [InlineKeyboardButton(text=f"مدت: {days} روز", callback_data="admin:trial:days")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:settings")],
        ]
    )
    await _edit_callback_message(callback, with_footer("تنظیمات تست رایگان"), reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "admin:trial:toggle")
async def admin_trial_toggle(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        enabled = await repository.get_trial_enabled()
        await repository.set_trial_enabled(not enabled)
        await sync_bot_commands(callback.bot, repository)
    await admin_trial_settings(callback, ctx)


@router.callback_query(F.data == "admin:discounts")
async def admin_discounts_list(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await _render_discounts_list(callback, ctx)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^discount:view:\d+$"))
async def admin_discount_view(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    code_id = int(callback.data.rsplit(":", 1)[-1])
    await _render_discount_detail(callback, ctx, code_id)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^discount:edit:\d+:(percent|max_uses|valid_days)$"))
async def admin_discount_edit_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    _, _, raw_id, field = callback.data.split(":", 3)
    code_id = int(raw_id)
    async with ctx.database.session() as db:
        code = await Repository(db).get_discount_code_by_id(code_id)
    if code is None:
        await callback.answer("کد پیدا نشد.", show_alert=True)
        return
    await state.update_data(discount_edit_id=code_id)
    if field == "percent":
        await state.set_state(DiscountEdit.percent)
        prompt = f"درصد جدید برای {code.code.upper()} را بفرستید (۰ تا ۱۰۰)."
        markup = admin_discount_detail_keyboard(code_id)
    elif field == "max_uses":
        await state.set_state(DiscountEdit.max_uses)
        prompt = f"حداکثر استفاده جدید برای {code.code.upper()} را بفرستید یا نامحدود را بزنید."
        markup = admin_discount_edit_max_uses_keyboard(code_id)
    else:
        await state.set_state(DiscountEdit.valid_days)
        prompt = f"مدت اعتبار جدید به روز برای {code.code.upper()} را بفرستید یا نامحدود را بزنید."
        markup = admin_discount_edit_valid_days_keyboard(code_id)
    await _edit_callback_message(callback, with_footer(prompt), reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^discount:edit:\d+:max_uses:0$"))
async def admin_discount_edit_max_uses_unlimited(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    if await state.get_state() != DiscountEdit.max_uses.state:
        await callback.answer()
        return
    data = await state.get_data()
    code_id = int(data.get("discount_edit_id") or 0)
    async with ctx.database.session() as db:
        try:
            updated = await Repository(db).update_discount_code(code_id, max_uses=0)
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
    if updated is None:
        await callback.answer("کد پیدا نشد.", show_alert=True)
        return
    await state.clear()
    await callback.answer("سقف استفاده نامحدود شد.")
    await _render_discount_detail(callback, ctx, code_id)


@router.callback_query(F.data.regexp(r"^discount:edit:\d+:valid_days:0$"))
async def admin_discount_edit_valid_days_unlimited(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    if await state.get_state() != DiscountEdit.valid_days.state:
        await callback.answer()
        return
    data = await state.get_data()
    code_id = int(data.get("discount_edit_id") or 0)
    async with ctx.database.session() as db:
        try:
            updated = await Repository(db).update_discount_code(code_id, valid_days=0)
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
    if updated is None:
        await callback.answer("کد پیدا نشد.", show_alert=True)
        return
    await state.clear()
    await callback.answer("مدت اعتبار نامحدود شد.")
    await _render_discount_detail(callback, ctx, code_id)


@router.message(DiscountEdit.percent)
async def admin_discount_edit_percent(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    data = await state.get_data()
    code_id = int(data.get("discount_edit_id") or 0)
    try:
        percent = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد معتبر نیست.")
        return
    if percent < 0 or percent > 100:
        await message.answer("درصد باید بین ۰ تا ۱۰۰ باشد.")
        return
    async with ctx.database.session() as db:
        updated = await Repository(db).update_discount_code(code_id, discount_percent=percent)
    await state.clear()
    if updated is None:
        await message.answer("کد پیدا نشد.", reply_markup=admin_back_keyboard())
        return
    await message.answer("درصد کد تخفیف به‌روز شد.")
    await _render_discount_detail(message, ctx, code_id)


@router.message(DiscountEdit.max_uses)
async def admin_discount_edit_max_uses(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    data = await state.get_data()
    code_id = int(data.get("discount_edit_id") or 0)
    try:
        max_uses = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد معتبر نیست.", reply_markup=admin_discount_edit_max_uses_keyboard(code_id))
        return
    if max_uses < 0:
        await message.answer("تعداد استفاده نمی‌تواند منفی باشد.", reply_markup=admin_discount_edit_max_uses_keyboard(code_id))
        return
    async with ctx.database.session() as db:
        try:
            updated = await Repository(db).update_discount_code(code_id, max_uses=max_uses)
        except ValueError as exc:
            if str(exc) == "discount_max_uses_below_used_count":
                await message.answer("سقف استفاده نمی‌تواند کمتر از تعداد استفاده‌شده باشد.", reply_markup=admin_discount_edit_max_uses_keyboard(code_id))
                return
            await message.answer("مقدار نامعتبر است.", reply_markup=admin_discount_edit_max_uses_keyboard(code_id))
            return
    await state.clear()
    if updated is None:
        await message.answer("کد پیدا نشد.", reply_markup=admin_back_keyboard())
        return
    await message.answer("سقف استفاده به‌روز شد.")
    await _render_discount_detail(message, ctx, code_id)


@router.message(DiscountEdit.valid_days)
async def admin_discount_edit_valid_days(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    data = await state.get_data()
    code_id = int(data.get("discount_edit_id") or 0)
    try:
        valid_days = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد معتبر نیست.", reply_markup=admin_discount_edit_valid_days_keyboard(code_id))
        return
    if valid_days < 0:
        await message.answer("تعداد روز نمی‌تواند منفی باشد.", reply_markup=admin_discount_edit_valid_days_keyboard(code_id))
        return
    async with ctx.database.session() as db:
        updated = await Repository(db).update_discount_code(code_id, valid_days=valid_days)
    await state.clear()
    if updated is None:
        await message.answer("کد پیدا نشد.", reply_markup=admin_back_keyboard())
        return
    await message.answer("مدت اعتبار به‌روز شد.")
    await _render_discount_detail(message, ctx, code_id)


@router.callback_query(F.data.regexp(r"^discount:del:\d+$"))
async def admin_discount_delete_confirm(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    code_id = int(callback.data.rsplit(":", 1)[-1])
    async with ctx.database.session() as db:
        code = await Repository(db).get_discount_code_by_id(code_id)
    if code is None:
        await callback.answer("کد پیدا نشد.", show_alert=True)
        return
    await _edit_callback_message(
        callback,
        with_footer(f"کد {code.code.upper()} حذف شود؟\n\nکد غیرفعال می‌شود و دیگر قابل استفاده نیست."),
        reply_markup=admin_discount_delete_confirm_keyboard(code_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^discount:del:\d+:yes$"))
async def admin_discount_delete(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    code_id = int(callback.data.split(":")[2])
    async with ctx.database.session() as db:
        deleted = await Repository(db).deactivate_discount_code(code_id)
    if not deleted:
        await callback.answer("کد پیدا نشد.", show_alert=True)
        return
    await callback.answer("کد حذف شد.")
    await _render_discounts_list(callback, ctx)


@router.callback_query(F.data == "admin:discounts:add")
async def admin_discount_add_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(DiscountCreate.code)
    await _edit_callback_message(callback, with_footer("کد تخفیف را بفرستید."), reply_markup=admin_back_keyboard())
    await callback.answer()


@router.message(DiscountCreate.code)
async def admin_discount_code(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    await state.update_data(discount_code=(message.text or "").strip())
    await state.set_state(DiscountCreate.percent)
    await message.answer("درصد تخفیف (۰ تا ۱۰۰) را بفرستید.")


@router.message(DiscountCreate.percent)
async def admin_discount_percent(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    try:
        percent = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد معتبر نیست.")
        return
    if percent < 0 or percent > 100:
        await message.answer("درصد باید بین ۰ تا ۱۰۰ باشد.")
        return
    await state.update_data(discount_percent=percent)
    await state.set_state(DiscountCreate.max_uses)
    await _prompt_discount_max_uses(message)


@router.callback_query(F.data == "discount:max_uses:0")
async def admin_discount_max_uses_unlimited(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    if await state.get_state() != DiscountCreate.max_uses.state:
        await callback.answer()
        return
    await state.update_data(discount_max_uses=0)
    await state.set_state(DiscountCreate.valid_days)
    await callback.answer("تعداد استفاده نامحدود شد.")
    await _prompt_discount_valid_days(callback.message)


@router.message(DiscountCreate.max_uses)
async def admin_discount_max_uses(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    try:
        max_uses = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد معتبر نیست.", reply_markup=admin_discount_max_uses_keyboard())
        return
    if max_uses < 0:
        await message.answer("تعداد استفاده نمی‌تواند منفی باشد.", reply_markup=admin_discount_max_uses_keyboard())
        return
    await state.update_data(discount_max_uses=max_uses)
    await state.set_state(DiscountCreate.valid_days)
    await _prompt_discount_valid_days(message)


@router.callback_query(F.data == "discount:valid_days:0")
async def admin_discount_valid_days_unlimited(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    if await state.get_state() != DiscountCreate.valid_days.state:
        await callback.answer()
        return
    await callback.answer("مدت اعتبار نامحدود شد.")
    await _create_discount_from_state(callback.message, state, ctx, valid_days=0)


@router.message(DiscountCreate.valid_days)
async def admin_discount_valid_days(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    try:
        valid_days = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد معتبر نیست.", reply_markup=admin_discount_valid_days_keyboard())
        return
    if valid_days < 0:
        await message.answer("تعداد روز نمی‌تواند منفی باشد.", reply_markup=admin_discount_valid_days_keyboard())
        return
    await _create_discount_from_state(message, state, ctx, valid_days=valid_days)


@router.callback_query(F.data == "admin:tickets")
async def admin_tickets_list(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        tickets = await Repository(db).list_open_tickets()
    lines = ["تیکت‌های باز", ""]
    if not tickets:
        lines.append("تیکتی نیست.")
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    rows = []
    for ticket in tickets[:15]:
        rows.append([InlineKeyboardButton(text=f"#{ticket.id} {ticket.subject[:30]}", callback_data=f"admin:ticket:{ticket.id}")])
    rows.append([InlineKeyboardButton(text="بازگشت", callback_data="admin:panel")])
    await _edit_callback_message(callback, with_footer("\n".join(lines) if lines else "تیکت‌ها"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:ticket:\d+$"))
async def admin_ticket_detail(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    ticket_id = int(callback.data.rsplit(":", 1)[-1])
    async with ctx.database.session() as db:
        repository = Repository(db)
        ticket = await repository.get_ticket(ticket_id)
        messages = await repository.list_ticket_messages(ticket_id)
    lines = [f"تیکت #{ticket.id}: {ticket.subject}", ""]
    for item in messages[-10:]:
        role = "کاربر" if item.sender_role == "buyer" else "ادمین"
        lines.append(f"{role}: {item.text}")
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="پاسخ", callback_data=f"admin:ticket:{ticket_id}:reply")],
            [InlineKeyboardButton(text="بستن تیکت", callback_data=f"admin:ticket:{ticket_id}:close")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:tickets")],
        ]
    )
    await state.update_data(admin_ticket_id=ticket_id)
    await _edit_callback_message(callback, with_footer("\n".join(lines)), reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:ticket:\d+:reply$"))
async def admin_ticket_reply_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    ticket_id = int(callback.data.split(":")[2])
    await state.set_state(TicketReply.text)
    await state.update_data(admin_ticket_id=ticket_id)
    await callback.answer("متن پاسخ را بفرستید.")


@router.message(TicketReply.text)
async def admin_ticket_reply_send(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    data = await state.get_data()
    ticket_id = int(data.get("admin_ticket_id") or 0)
    text = (message.text or "").strip()
    if not text:
        await message.answer("متن خالی است.")
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        ticket = await repository.get_ticket(ticket_id)
        await repository.add_ticket_message(ticket_id, sender_role="admin", text=text)
        user = await repository.get_user(ticket.user_id)
    await state.clear()
    if user:
        try:
            await message.bot.send_message(user.telegram_id, f"پاسخ پشتیبانی:\n{text}")
        except Exception:
            pass
    await message.answer("پاسخ ثبت و ارسال شد.", reply_markup=admin_back_keyboard())


@router.callback_query(F.data.regexp(r"^admin:ticket:\d+:close$"))
async def admin_ticket_close(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    ticket_id = int(callback.data.split(":")[2])
    async with ctx.database.session() as db:
        await Repository(db).close_ticket(ticket_id)
    await admin_tickets_list(callback, ctx)
