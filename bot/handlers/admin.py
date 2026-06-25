from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import constants as c
from bot.admin_users import notify_wallet_admin_adjustment
from bot.context import AppContext
from bot.db import Repository, normalize_support_username
from bot.formatting import with_footer
from bot.notifications import notify_wallet_payment_review
from bot.keyboards import admin_back_keyboard, admin_earning_keyboard, admin_menu, admin_pricing_keyboard, back_to_main_keyboard, main_menu, wallet_after_approval_keyboard
from bot.states import Broadcast, EarningEdit, PricingEdit, SupportEdit

router = Router()


async def _edit_callback_message(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def _earning_settings_text(enabled: bool, percent: int) -> str:
    return (
        "تنظیمات کسب درآمد\n"
        f"وضعیت: {'فعال' if enabled else 'غیرفعال'}\n"
        f"پورسانت خرید جدید: {percent}٪\n\n"
        "پورسانت فقط برای خرید اشتراک جدید محاسبه می‌شود و تمدید اشتراک پورسانت ندارد."
    )


async def require_admin(message: Message, ctx: AppContext) -> bool:
    if message.from_user.id not in ctx.settings.admin_ids:
        await message.answer("دسترسی ادمین ندارید.", reply_markup=back_to_main_keyboard())
        return False
    return True


@router.message(F.text == c.ADMIN_PANEL)
async def admin_panel(message: Message, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    await message.answer(with_footer("پنل ادمین"), reply_markup=admin_menu())


@router.callback_query(F.data == "admin:panel")
async def admin_panel_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await _edit_callback_message(callback, with_footer("پنل ادمین"), reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:quota")
async def admin_quota(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        quota = await ctx.quota.status(Repository(db))
    if quota is None:
        text = "ظرفیت فروش از مستر بات متصل نشده است."
    else:
        text = "\n".join(
            [
                "ظرفیت فروش ربات",
                f"سقف کل: {quota.limit_gb} گیگ",
                f"مصرف‌شده: {quota.used_gb} گیگ",
                f"باقی‌مانده: {quota.remaining_gb} گیگ",
                "",
                "افزایش ظرفیت فقط از ربات مستر انجام می‌شود.",
            ]
        )
    await _edit_callback_message(callback, with_footer(text), reply_markup=admin_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:support")
async def support_setting_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        current = await Repository(db).get_support_username()
    current_text = f"فعلی: @{current}\n" if current else "فعلا تنظیم نشده است.\n"
    await state.set_state(SupportEdit.username)
    await _edit_callback_message(
        callback,
        current_text
        + "یوزرنیم پشتیبانی را ارسال کنید.\n"
        + "فرمت قابل قبول: @username یا username یا https://t.me/username",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(SupportEdit.username)
async def support_setting_finish(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    normalized = normalize_support_username(message.text)
    if not normalized:
        await message.answer("یوزرنیم معتبر نیست. فقط حروف انگلیسی، عدد و _ با طول 5 تا 32 مجاز است.", reply_markup=admin_back_keyboard())
        return
    async with ctx.database.session() as db:
        await Repository(db).set_support_username(normalized)
    await state.clear()
    await message.answer(f"پشتیبانی تنظیم شد:\nhttps://t.me/{normalized}", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:earning")
async def earning_settings(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        enabled = await repository.get_earning_enabled()
        percent = await repository.get_earning_percent()
    await _edit_callback_message(
        callback,
        with_footer(_earning_settings_text(enabled, percent)),
        reply_markup=admin_earning_keyboard(enabled, percent),
    )
    await callback.answer()


@router.callback_query(F.data == "earning:toggle")
async def earning_toggle(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        enabled = not await repository.get_earning_enabled()
        await repository.set_earning_enabled(enabled)
        percent = await repository.get_earning_percent()
    await _edit_callback_message(
        callback,
        with_footer(_earning_settings_text(enabled, percent)),
        reply_markup=admin_earning_keyboard(enabled, percent),
    )
    await callback.answer()


@router.callback_query(F.data == "earning:set_percent")
async def earning_percent_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(EarningEdit.percent)
    await _edit_callback_message(callback, "درصد پورسانت خرید جدید را از 0 تا 100 وارد کنید.", reply_markup=admin_back_keyboard())
    await callback.answer()


@router.message(EarningEdit.percent)
async def earning_percent_finish(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    try:
        percent = int((message.text or "").strip())
    except ValueError:
        await message.answer("درصد پورسانت را عددی وارد کنید.", reply_markup=admin_back_keyboard())
        return
    if percent < 0 or percent > 100:
        await message.answer("درصد پورسانت باید بین 0 تا 100 باشد.", reply_markup=admin_back_keyboard())
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        await repository.set_earning_percent(percent)
        enabled = await repository.get_earning_enabled()
    await state.clear()
    await message.answer(
        with_footer("درصد پورسانت ثبت شد."),
        reply_markup=admin_earning_keyboard(enabled, percent),
    )


@router.message(F.text == c.ADMIN_PLANS)
async def manage_plans(message: Message, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        settings = await repository.get_pricing_settings()
        presets = await repository.list_traffic_presets()
    await message.answer(with_footer("تنظیمات پلن ها"), reply_markup=admin_pricing_keyboard(settings, presets))


@router.callback_query(F.data == "admin:plans")
async def manage_plans_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        settings = await repository.get_pricing_settings()
        presets = await repository.list_traffic_presets()
    await _edit_callback_message(callback, with_footer("تنظیمات پلن ها"), reply_markup=admin_pricing_keyboard(settings, presets))
    await callback.answer()


@router.callback_query(F.data == "pricing:set_per_gb")
async def set_per_gb_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(PricingEdit.per_gb_price)
    await _edit_callback_message(callback, "قیمت هر گیگ را به تومان وارد کنید.", reply_markup=admin_back_keyboard())
    await callback.answer()


@router.message(PricingEdit.per_gb_price)
async def set_per_gb_finish(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    try:
        price = int((message.text or "").replace(",", "").strip())
    except ValueError:
        await message.answer("قیمت را عددی وارد کنید.", reply_markup=admin_back_keyboard())
        return
    if price < 0:
        await message.answer("قیمت نمی‌تواند منفی باشد.", reply_markup=admin_back_keyboard())
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        await repository.update_pricing_settings(per_gb_price=price)
        settings = await repository.get_pricing_settings()
        presets = await repository.list_traffic_presets()
    await state.clear()
    await message.answer(with_footer("قیمت هر گیگ ثبت شد."), reply_markup=admin_pricing_keyboard(settings, presets))


@router.callback_query(F.data == "pricing:set_3m")
async def set_three_month_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(PricingEdit.three_month_extra_price)
    await _edit_callback_message(callback, "هزینه اضافه سه ماهه را به تومان وارد کنید.", reply_markup=admin_back_keyboard())
    await callback.answer()


@router.message(PricingEdit.three_month_extra_price)
async def set_three_month_finish(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    try:
        price = int((message.text or "").replace(",", "").strip())
    except ValueError:
        await message.answer("قیمت را عددی وارد کنید.", reply_markup=admin_back_keyboard())
        return
    if price < 0:
        await message.answer("قیمت نمی‌تواند منفی باشد.", reply_markup=admin_back_keyboard())
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        await repository.update_pricing_settings(three_month_extra_price=price)
        settings = await repository.get_pricing_settings()
        presets = await repository.list_traffic_presets()
    await state.clear()
    await message.answer(with_footer("هزینه سه ماهه ثبت شد."), reply_markup=admin_pricing_keyboard(settings, presets))


@router.callback_query(F.data == "pricing:toggle_1m")
async def toggle_one_month(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        current = await repository.get_pricing_settings()
        settings = await repository.update_pricing_settings(one_month_enabled=not current.one_month_enabled)
        presets = await repository.list_traffic_presets()
    await _edit_callback_message(callback, with_footer("وضعیت یک ماهه تغییر کرد."), reply_markup=admin_pricing_keyboard(settings, presets))
    await callback.answer()


@router.callback_query(F.data == "pricing:toggle_3m")
async def toggle_three_month(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        current = await repository.get_pricing_settings()
        settings = await repository.update_pricing_settings(three_month_enabled=not current.three_month_enabled)
        presets = await repository.list_traffic_presets()
    await _edit_callback_message(callback, with_footer("وضعیت سه ماهه تغییر کرد."), reply_markup=admin_pricing_keyboard(settings, presets))
    await callback.answer()


@router.callback_query(F.data.startswith("pricing:preset:"))
async def preset_discount_start(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    gb = int(callback.data.split(":")[2])
    await state.update_data(preset_gb=gb)
    await state.set_state(PricingEdit.preset_discount)
    await _edit_callback_message(callback, f"درصد تخفیف برای {gb}GB را از 0 تا 100 وارد کنید.", reply_markup=admin_back_keyboard())
    await callback.answer()


@router.message(PricingEdit.preset_discount)
async def preset_discount_finish(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    try:
        discount = int((message.text or "").strip())
    except ValueError:
        await message.answer("درصد تخفیف را عددی وارد کنید.", reply_markup=admin_back_keyboard())
        return
    if discount < 0 or discount > 100:
        await message.answer("درصد تخفیف باید بین 0 تا 100 باشد.", reply_markup=admin_back_keyboard())
        return
    data = await state.get_data()
    gb = int(data["preset_gb"])
    async with ctx.database.session() as db:
        repository = Repository(db)
        await repository.update_preset_discount(gb, discount)
        settings = await repository.get_pricing_settings()
        presets = await repository.list_traffic_presets()
    await state.clear()
    await message.answer(with_footer("تخفیف ثبت شد."), reply_markup=admin_pricing_keyboard(settings, presets))


@router.message(F.text == c.ADMIN_USERS)
async def users(message: Message, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    from bot.handlers.admin_users import _render_users_list

    await _render_users_list(message, ctx, page=1)


@router.message(F.text.startswith("/adjust"))
async def adjust_wallet_command(message: Message, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    await message.answer(
        "دستور /adjust منسوخ شده است.\nاز پنل ادمین → کاربران → شارژ کیف پول استفاده کنید.",
        reply_markup=admin_back_keyboard(),
    )


@router.message(F.text == c.ADMIN_PAYMENTS)
async def pending_payments(message: Message, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    from bot.handlers.admin_payments import _render_payments_list_message

    await _render_payments_list_message(message, ctx, page=1)


@router.callback_query(F.data.startswith("pay_ok:") | F.data.startswith("pay_no:"))
async def review_payment(callback: CallbackQuery, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    action, raw_id = callback.data.split(":", 1)
    approved = action == "pay_ok"
    async with ctx.database.session() as db:
        repository = Repository(db)
        admin_user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        payment = await repository.review_payment(int(raw_id), admin_user.id, approved)
        buyer = await repository.get_user(payment.user_id) if payment else None
        balance = buyer.wallet_balance if buyer and approved else 0
    if not payment:
        await callback.answer("این پرداخت قبلا بررسی شده یا پیدا نشد.", show_alert=True)
        return
    if buyer:
        await notify_wallet_payment_review(
            callback.bot,
            buyer,
            amount=payment.amount,
            approved=approved,
            balance=balance,
        )
    await callback.answer("ثبت شد.", show_alert=True)
    status = "تایید شد" if approved else "رد شد"
    if callback.message.photo:
        await callback.message.edit_caption((callback.message.caption or "") + f"\nوضعیت: {status}", reply_markup=admin_back_keyboard())
    else:
        await _edit_callback_message(callback, (callback.message.text or "") + f"\n\nوضعیت: {status}", reply_markup=admin_back_keyboard())


@router.message(F.text == c.ADMIN_BROADCAST)
async def broadcast_start(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    await state.set_state(Broadcast.text)
    await message.answer("متن پیام همگانی را ارسال کنید.", reply_markup=admin_back_keyboard())


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_start_callback(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if callback.from_user.id not in ctx.settings.admin_ids:
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(Broadcast.text)
    await _edit_callback_message(callback, "متن پیام همگانی را ارسال کنید.", reply_markup=admin_back_keyboard())
    await callback.answer()


@router.message(Broadcast.text)
async def broadcast_send(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not await require_admin(message, ctx):
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        users_list = await repository.list_users(10000)
        support_username = await repository.get_support_username()
        earning_enabled = await repository.get_earning_enabled()
    sent = 0
    for user in users_list:
        try:
            await message.bot.send_message(user.telegram_id, message.text, reply_markup=back_to_main_keyboard())
            sent += 1
        except Exception:
            continue
    await state.clear()
    await message.answer(with_footer(f"پیام برای {sent} کاربر ارسال شد."), reply_markup=main_menu(True, ctx.settings.web_app_url, support_username, earning_enabled))
