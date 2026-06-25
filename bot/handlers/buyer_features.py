from __future__ import annotations

from math import ceil

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import constants as c
from bot.context import AppContext
from bot.db import Repository
from bot.formatting import with_footer
from bot.keyboards import back_to_main_keyboard, subscription_detail_keyboard, wallet_ledger_keyboard, wallet_top_up_keyboard
from bot.marzban import MarzbanError
from bot.menu_helpers import main_menu_for_user
from bot.notifications import wallet_reason_label
from bot.states import BuyerTicketReply, TicketCreate, TicketReply
from bot.handlers.buyer import (
    _edit_callback_message,
    get_owned_subscription,
)

router = Router()
LEDGER_PER_PAGE = 8


def _ledger_pages(total: int) -> int:
    return max(1, ceil(total / LEDGER_PER_PAGE))


def _ledger_text(*, balance: int, lines: list[str], page: int, total_pages: int) -> str:
    body = "\n".join(["تاریخچه کیف پول", "", f"موجودی: {balance:,} تومان", ""] + lines)
    if total_pages > 1:
        body += f"\n\nصفحه {page} از {total_pages}"
    return body


@router.callback_query(F.data == "menu:tickets")
async def tickets_menu(callback: CallbackQuery, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        tickets = await repository.list_user_tickets(user.id)
    rows = [[InlineKeyboardButton(text="➕ تیکت جدید", callback_data="ticket:new")]]
    for ticket in tickets[:10]:
        rows.append([InlineKeyboardButton(text=f"#{ticket.id} {ticket.subject[:25]}", callback_data=f"ticket:{ticket.id}")])
    rows.append([InlineKeyboardButton(text=c.BACK, callback_data="menu:home")])
    await _edit_callback_message(callback, with_footer("پشتیبانی / تیکت‌ها"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "ticket:new")
async def ticket_new_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TicketCreate.subject)
    await _edit_callback_message(callback, with_footer("موضوع تیکت را بفرستید."), reply_markup=back_to_main_keyboard())
    await callback.answer()


@router.message(TicketCreate.subject)
async def ticket_new_subject(message: Message, state: FSMContext) -> None:
    await state.update_data(ticket_subject=(message.text or "").strip())
    await state.set_state(TicketCreate.text)
    await message.answer("متن پیام را بفرستید.")


@router.message(TicketCreate.text)
async def ticket_new_finish(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    subject = str(data.get("ticket_subject") or "بدون موضوع")
    text = (message.text or "").strip()
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        ticket = await repository.create_ticket(user.id, subject, text)
    await state.clear()
    for admin_id in ctx.settings.admin_ids:
        try:
            await message.bot.send_message(admin_id, f"تیکت جدید #{ticket.id}\n{subject}\n{text}")
        except Exception:
            pass
    await message.answer("تیکت ثبت شد.", reply_markup=back_to_main_keyboard())


@router.callback_query(F.data.regexp(r"^ticket:\d+$"))
async def ticket_detail(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    ticket_id = int(callback.data.split(":")[1])
    async with ctx.database.session() as db:
        messages = await Repository(db).list_ticket_messages(ticket_id)
    lines = [f"تیکت #{ticket_id}", ""]
    for item in messages[-10:]:
        role = "شما" if item.sender_role == "buyer" else "پشتیبانی"
        lines.append(f"{role}: {item.text}")
    await state.update_data(buyer_ticket_id=ticket_id)
    await state.set_state(BuyerTicketReply.text)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c.BACK, callback_data="menu:tickets")]])
    await _edit_callback_message(callback, with_footer("\n".join(lines) + "\n\nبرای پاسخ، پیام بفرستید."), reply_markup=markup)
    await callback.answer()


@router.message(BuyerTicketReply.text, F.chat.type == "private")
async def ticket_buyer_reply(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if message.from_user.id in ctx.settings.admin_ids:
        return
    data = await state.get_data()
    ticket_id = int(data.get("buyer_ticket_id") or 0)
    if not ticket_id:
        return
    text = (message.text or "").strip()
    if not text:
        return
    async with ctx.database.session() as db:
        await Repository(db).add_ticket_message(ticket_id, sender_role="buyer", text=text)
    for admin_id in ctx.settings.admin_ids:
        try:
            await message.bot.send_message(admin_id, f"پاسخ تیکت #{ticket_id}:\n{text}")
        except Exception:
            pass
    await state.clear()
    await message.answer("پیام شما ثبت شد.", reply_markup=back_to_main_keyboard())


@router.callback_query(F.data.startswith("wallet:ledger:"))
async def wallet_ledger_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    page = int(callback.data.rsplit(":", 1)[-1])
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        total = await repository.count_wallet_transactions(user.id)
        offset = (max(page, 1) - 1) * LEDGER_PER_PAGE
        items = await repository.list_wallet_transactions(user.id, limit=LEDGER_PER_PAGE, offset=offset)
    lines = []
    for item in items:
        sign = "+" if item.amount >= 0 else ""
        lines.append(f"{sign}{item.amount:,} · {wallet_reason_label(item.reason)} · {item.created_at[:16]}")
    if not lines:
        lines.append("تراکنشی ثبت نشده است.")
    await _edit_callback_message(
        callback,
        with_footer(_ledger_text(balance=user.wallet_balance, lines=lines, page=page, total_pages=_ledger_pages(total))),
        reply_markup=wallet_ledger_keyboard(page=page, total_pages=_ledger_pages(total), scope="wallet", scope_id=0),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:trial")
async def trial_start(callback: CallbackQuery, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        if not await repository.get_trial_enabled():
            await callback.answer("تست رایگان فعال نیست.", show_alert=True)
            return
        if await repository.has_trial_grant(user.id):
            await callback.answer("قبلاً تست رایگان دریافت کرده‌اید.", show_alert=True)
            return
        gb = await repository.get_trial_traffic_gb()
        days = await repository.get_trial_days()
        offer = repository.build_offer(await repository.get_pricing_settings(), gb, days, "trial", 100)
        subscription = None
        marzban_sub = None
        try:
            await ctx.quota.ensure_available(repository, requested_gb=gb)
            marzban_sub = await ctx.marzban.create_subscription(f"trial_{user.telegram_id}", gb, days)
            await repository.grant_trial(user.id)
            subscription = await repository.create_subscription_after_charge(user, offer, marzban_sub.username, marzban_sub.subscription_url, marzban_sub.expires_at)
            await db.commit()
        except (MarzbanError, ValueError) as exc:
            await callback.answer(str(exc)[:180], show_alert=True)
            return
    if subscription is None or marzban_sub is None:
        await callback.answer("خطا در فعال‌سازی تست.", show_alert=True)
        return
    await _edit_callback_message(
        callback,
        with_footer(f"تست رایگان فعال شد.\n{gb}GB / {days} روز\n\n{marzban_sub.subscription_url}"),
        reply_markup=subscription_detail_keyboard(subscription.id),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:support")
async def support_callback_fixed(callback: CallbackQuery, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        support_username = await Repository(db).get_support_username()
    if support_username:
        text = f"{ctx.settings.support_text}\n\nپشتیبانی: @{support_username}"
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=c.SUPPORT, url=f"https://t.me/{support_username}")],
                [InlineKeyboardButton(text="تیکت", callback_data="menu:tickets")],
                [InlineKeyboardButton(text=c.BACK, callback_data="menu:home")],
            ]
        )
    else:
        text = f"{ctx.settings.support_text}\n\nاز بخش تیکت پیام بفرستید."
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="تیکت", callback_data="menu:tickets")],
                [InlineKeyboardButton(text=c.BACK, callback_data="menu:home")],
            ]
        )
    await _edit_callback_message(callback, with_footer(text), reply_markup=markup)
    await callback.answer()
