from __future__ import annotations

from math import ceil

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.context import AppContext
from bot.db import Repository
from bot.formatting import with_footer
from bot.handlers.admin import _edit_callback_message, require_admin
from bot.keyboards import admin_back_keyboard
from bot.forced_join import resolve_required_chat
from bot.states import DiscountCreate, ForcedJoinAdd, TicketReply

router = Router()

LEDGER_PER_PAGE = 8


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
    await message.answer(f"کانال «{title}» اضافه شد.", reply_markup=admin_back_keyboard())


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
        gb = await repository.get_trial_traffic_gb()
        days = await repository.get_trial_days()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"وضعیت: {'فعال' if enabled else 'غیرفعال'}", callback_data="admin:trial:toggle")],
            [InlineKeyboardButton(text=f"حجم: {gb} GB", callback_data="admin:trial:gb")],
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
    await admin_trial_settings(callback, ctx)


@router.callback_query(F.data == "admin:discounts")
async def admin_discounts_list(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        codes = await Repository(db).list_discount_codes()
    lines = ["کدهای تخفیف", ""]
    if not codes:
        lines.append("کدی ثبت نشده است.")
    else:
        for code in codes[:20]:
            lines.append(f"• {code.code.upper()} — {code.discount_percent}٪ — {code.used_count}/{code.max_uses or '∞'}")
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ کد جدید", callback_data="admin:discounts:add")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:settings")],
        ]
    )
    await _edit_callback_message(callback, with_footer("\n".join(lines)), reply_markup=markup)
    await callback.answer()


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
    data = await state.get_data()
    try:
        percent = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد معتبر نیست.")
        return
    async with ctx.database.session() as db:
        await Repository(db).create_discount_code(str(data["discount_code"]), percent)
    await state.clear()
    await message.answer("کد تخفیف ایجاد شد.", reply_markup=admin_back_keyboard())


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
