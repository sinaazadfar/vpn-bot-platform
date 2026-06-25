from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.admin_users import (
    USERS_PER_PAGE,
    admin_user_detail_keyboard,
    admin_user_wallet_keyboard,
    admin_users_list_keyboard,
    user_detail_text,
    user_display_name,
    user_subscriptions_text,
    users_list_text,
)
from bot.context import AppContext
from bot.db import Repository
from bot.formatting import with_footer
from bot.handlers.admin import _edit_callback_message, require_admin
from bot.keyboards import admin_back_keyboard
from bot.states import AdminUserMessage, AdminUserSearch, AdminUserWallet
from bot.user_profile import refresh_user_profile_from_telegram, refresh_users_profiles_from_telegram

router = Router()


def _is_admin(callback_or_message, ctx: AppContext) -> bool:
    user = callback_or_message.from_user
    return user is not None and user.id in ctx.settings.admin_ids


async def _render_users_list(
    target: CallbackQuery | Message,
    ctx: AppContext,
    *,
    page: int = 1,
    search_query: str | None = None,
    search_results=None,
) -> None:
    bot = target.bot
    async with ctx.database.session() as db:
        repository = Repository(db)
        if search_query is not None:
            users = search_results if search_results is not None else await repository.search_users(search_query, limit=20)
            total_users = len(users)
            display_page = 1
        else:
            total_users = await repository.count_users()
            display_page = page
            users = await repository.list_users_page(page=page, per_page=USERS_PER_PAGE)
        users = await refresh_users_profiles_from_telegram(bot, repository, users)
    text = with_footer(users_list_text(users=users, page=display_page, total_users=total_users, search_query=search_query))
    markup = admin_users_list_keyboard(users=users, page=display_page, total_users=total_users, search_query=search_query)
    if isinstance(target, CallbackQuery):
        await _edit_callback_message(target, text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


async def _render_user_detail(callback: CallbackQuery, ctx: AppContext, user_id: int) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.get_user(user_id)
        if user is None:
            await callback.answer("کاربر پیدا نشد.", show_alert=True)
            return
        user = await refresh_user_profile_from_telegram(callback.bot, repository, user)
        subscription_count = await repository.count_user_subscriptions(user.id)
    await _edit_callback_message(
        callback,
        with_footer(user_detail_text(user=user, subscription_count=subscription_count)),
        reply_markup=admin_user_detail_keyboard(user=user),
    )


@router.callback_query(F.data == "admin:users")
@router.callback_query(F.data.startswith("adm:users:page:"))
async def users_list_callback(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    page = 1
    if callback.data.startswith("adm:users:page:"):
        try:
            page = max(int(callback.data.rsplit(":", 1)[-1]), 1)
        except ValueError:
            page = 1
    await _render_users_list(callback, ctx, page=page)
    await callback.answer()


@router.callback_query(F.data == "adm:users:search")
async def users_search_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AdminUserSearch.query)
    await _edit_callback_message(
        callback,
        with_footer(
            "\n".join(
                [
                    "جستجوی کاربر",
                    "",
                    "نام، نام خانوادگی، یوزرنیم (@username) یا آیدی تلگرام را بفرستید.",
                    "برای انصراف /cancel بزنید.",
                ]
            )
        ),
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminUserSearch.query)
async def users_search_finish(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    query = (message.text or "").strip()
    if not query:
        await message.answer("عبارت جستجو خالی است.", reply_markup=admin_back_keyboard())
        return
    async with ctx.database.session() as db:
        results = await Repository(db).search_users(query, limit=20)
    await state.clear()
    if not results:
        await message.answer(with_footer(f"نتیجه‌ای برای «{query}» پیدا نشد."), reply_markup=admin_back_keyboard())
        return
    await _render_users_list(message, ctx, search_query=query, search_results=results)


@router.callback_query(F.data.regexp(r"^adm:user:\d+$"))
async def user_detail_callback(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    user_id = int(callback.data.rsplit(":", 1)[-1])
    await _render_user_detail(callback, ctx, user_id)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^adm:user:\d+:wallet$"))
async def user_wallet_menu(callback: CallbackQuery, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    async with ctx.database.session() as db:
        user = await Repository(db).get_user(user_id)
    if user is None:
        await callback.answer("کاربر پیدا نشد.", show_alert=True)
        return
    await _edit_callback_message(
        callback,
        with_footer(
            "\n".join(
                [
                    "شارژ کیف پول",
                    f"کاربر: {user_display_name(user)}",
                    f"موجودی فعلی: {user.wallet_balance:,} تومان",
                    "",
                    "یک مبلغ را انتخاب کنید یا مبلغ دلخواه بفرستید.",
                ]
            )
        ),
        reply_markup=admin_user_wallet_keyboard(user_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^adm:wallet:\d+:\d+$"))
async def user_wallet_quick_add(callback: CallbackQuery, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    _, _, raw_user_id, raw_amount = callback.data.split(":", 3)
    user_id = int(raw_user_id)
    amount = int(raw_amount)
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.get_user(user_id)
        if user is None:
            await callback.answer("کاربر پیدا نشد.", show_alert=True)
            return
        await repository.adjust_wallet(user_id, amount, "admin_adjust")
        await db.commit()
        user = await repository.get_user(user_id)
        subscription_count = await repository.count_user_subscriptions(user.id)
    await _edit_callback_message(
        callback,
        with_footer(user_detail_text(user=user, subscription_count=subscription_count)),
        reply_markup=admin_user_detail_keyboard(user=user),
    )
    await callback.answer(f"{amount:,} تومان اضافه شد.")


@router.callback_query(F.data.regexp(r"^adm:wallet:\d+:custom$"))
async def user_wallet_custom_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    await state.set_state(AdminUserWallet.amount)
    await state.update_data(admin_wallet_user_id=user_id)
    await _edit_callback_message(
        callback,
        with_footer("مبلغ شارژ را به تومان بفرستید (مثبت برای افزایش، منفی برای کسر)."),
        reply_markup=admin_user_wallet_keyboard(user_id),
    )
    await callback.answer()


@router.message(AdminUserWallet.amount)
async def user_wallet_custom_finish(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    data = await state.get_data()
    user_id = int(data.get("admin_wallet_user_id") or 0)
    raw = (message.text or "").strip().replace(",", "").replace("_", "")
    try:
        amount = int(raw)
    except ValueError:
        await message.answer("مبلغ معتبر نیست.", reply_markup=admin_user_wallet_keyboard(user_id))
        return
    if amount == 0:
        await message.answer("مبلغ نمی‌تواند صفر باشد.", reply_markup=admin_user_wallet_keyboard(user_id))
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.get_user(user_id)
        if user is None:
            await state.clear()
            await message.answer("کاربر پیدا نشد.", reply_markup=admin_back_keyboard())
            return
        await repository.adjust_wallet(user_id, amount, "admin_adjust")
        await db.commit()
        user = await repository.get_user(user_id)
        subscription_count = await repository.count_user_subscriptions(user.id)
    await state.clear()
    await message.answer(
        with_footer(user_detail_text(user=user, subscription_count=subscription_count)),
        reply_markup=admin_user_detail_keyboard(user=user),
    )


@router.callback_query(F.data.regexp(r"^adm:user:\d+:subs$"))
async def user_subscriptions_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.get_user(user_id)
        if user is None:
            await callback.answer("کاربر پیدا نشد.", show_alert=True)
            return
        subscriptions = await repository.list_user_subscriptions(user.id)
    await _edit_callback_message(
        callback,
        with_footer(user_subscriptions_text(user=user, subscriptions=subscriptions)),
        reply_markup=admin_user_detail_keyboard(user=user),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^adm:user:\d+:(ban|unban)$"))
async def user_toggle_ban(callback: CallbackQuery, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    parts = callback.data.split(":")
    user_id = int(parts[2])
    blocked = parts[3] == "ban"
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.set_user_blocked(user_id, blocked=blocked)
        if user is None:
            await callback.answer("امکان مسدود کردن این کاربر نیست.", show_alert=True)
            return
        subscription_count = await repository.count_user_subscriptions(user.id)
    await _edit_callback_message(
        callback,
        with_footer(user_detail_text(user=user, subscription_count=subscription_count)),
        reply_markup=admin_user_detail_keyboard(user=user),
    )
    await callback.answer("وضعیت کاربر به‌روز شد.")


@router.callback_query(F.data.regexp(r"^adm:user:\d+:message$"))
async def user_message_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    async with ctx.database.session() as db:
        user = await Repository(db).get_user(user_id)
    if user is None:
        await callback.answer("کاربر پیدا نشد.", show_alert=True)
        return
    await state.set_state(AdminUserMessage.text)
    await state.update_data(admin_message_user_id=user_id)
    await _edit_callback_message(
        callback,
        with_footer(f"متن پیام برای {user_display_name(user)} را بفرستید."),
        reply_markup=admin_user_detail_keyboard(user=user),
    )
    await callback.answer()


@router.message(AdminUserMessage.text)
async def user_message_send(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    data = await state.get_data()
    user_id = int(data.get("admin_message_user_id") or 0)
    text = (message.text or "").strip()
    if not text:
        await message.answer("متن پیام خالی است.")
        return
    async with ctx.database.session() as db:
        user = await Repository(db).get_user(user_id)
    if user is None:
        await state.clear()
        await message.answer("کاربر پیدا نشد.", reply_markup=admin_back_keyboard())
        return
    try:
        await message.bot.send_message(user.telegram_id, text)
    except Exception:
        await message.answer("ارسال پیام ناموفق بود. ممکن است کاربر ربات را بلاک کرده باشد.")
        return
    await state.clear()
    subscription_count = 0
    async with ctx.database.session() as db:
        subscription_count = await Repository(db).count_user_subscriptions(user.id)
    await message.answer(
        with_footer(f"پیام برای {user_display_name(user)} ارسال شد.\n\n{user_detail_text(user=user, subscription_count=subscription_count)}"),
        reply_markup=admin_user_detail_keyboard(user=user),
    )
