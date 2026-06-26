from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot import constants as c
from bot.connection_guides import (
    get_app,
    get_platform,
    guides_app_keyboard,
    guides_app_text,
    guides_apps_keyboard,
    guides_home_text,
    guides_platform_text,
    guides_platforms_keyboard,
)
from bot.configs import build_configs_txt, parse_v2ray_configs
from bot.discount_flow import discount_error_message, purchase_confirm_text
from bot.context import AppContext
from bot.db import User, Repository, Subscription, normalize_referral_code
from bot.formatting import html_code, html_pre, with_footer
from bot.keyboards import MAX_WALLET_TOP_UP, MIN_WALLET_TOP_UP, back_to_main_keyboard, confirm_extension_keyboard, confirm_purchase_keyboard, duration_keyboard, earn_details_keyboard, earn_keyboard, main_menu, payment_review_keyboard, profile_keyboard, purchase_coupon_keyboard, subscription_back_keyboard, subscription_configs_keyboard, subscription_detail_keyboard, subscriptions_page_keyboard, traffic_presets_keyboard, wallet_payment_keyboard, wallet_top_up_keyboard
from bot.marzban import MarzbanError
from bot.menu_helpers import main_menu_for_user
from bot.quota import VolumeQuotaError
from bot.qr import make_qr_png
from bot.states import PurchaseCoupon, PurchaseUsername, WalletTopUp
from bot.trial_flow import should_show_trial_button

router = Router()
SUBS_PER_PAGE = 10
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_PHOTO_CAPTION_LIMIT = 1024


def _subscription_link_text(subscription_url: str) -> str:
    return f"لینک اشتراک:\n{html_code(subscription_url)}"


def _config_text(index: int, config: str) -> str:
    return f"کانفیگ {index}:\n{html_code(config)}"


def _configs_text_chunks(configs: list[str]) -> list[str]:
    chunks: list[str] = []
    current_items: list[str] = []
    for index, config in enumerate(configs, start=1):
        item = f"{index}. {config}"
        candidate_items = [*current_items, item]
        candidate = f"همه کانفیگ‌ها:\n{html_pre('\n\n'.join(candidate_items))}"
        if len(with_footer(candidate)) > TELEGRAM_MESSAGE_LIMIT and current_items:
            chunks.append(f"همه کانفیگ‌ها:\n{html_pre('\n\n'.join(current_items))}")
            current_items = [item]
        else:
            current_items = candidate_items
    chunks.append(f"همه کانفیگ‌ها:\n{html_pre('\n\n'.join(current_items))}")
    return chunks


def _referral_invite_url(referral_code: str, bot_username: str) -> str:
    display_code = referral_code.upper()
    return f"https://t.me/{bot_username}?start={display_code}"


def _bot_display_name(*, first_name: str | None, username: str | None) -> str:
    if first_name and first_name.strip():
        return first_name.strip()
    if username:
        return f"@{username.lstrip('@')}"
    return "ربات"


def _earn_invite_instructions(earning_percent: int) -> str:
    example_purchase = 200_000
    example_commission = example_purchase * earning_percent // 100
    return (
        "دوستاتو دعوت کن، ازشون درآمد داشته باش!\n\n"
        "خلاصه‌ش اینه:\n"
        "۱) پیام پایین رو برای دوستات بفرست (یا فقط لینک داخلش رو کپی کن).\n"
        "۲) با لینک تو وارد ربات میشن و زیرمجموعه‌ات ثبت میشن.\n"
        f"۳) هر بار که پرداخت کنن، {earning_percent}٪ مبلغ پرداختشون تو کیف پولت میشینه.\n\n"
        "یه مثال:\n"
        f"دوستت اشتراک ۲۰۰,۰۰۰ تومنی بگیره → {example_commission:,} تومن برات.\n\n"
        "این متن رو بفرست:"
    )


def _earn_share_message(bot_name: str, invite_url: str) -> str:
    return (
        "سلام!\n"
        f"از ربات {bot_name} می‌تونی راحت اشتراک VPN بگیری. پشتیبانی‌شون عالیه و کیفیت‌شون خیلی خوبه 👌👌\n"
        f"{invite_url}"
    )


async def _send_earn_invite(message: Message, *, bot_name: str, invite_url: str, earning_percent: int) -> None:
    await message.answer(
        with_footer(_earn_invite_instructions(earning_percent)),
        reply_markup=earn_keyboard(),
        parse_mode="HTML",
    )
    await message.answer(_earn_share_message(bot_name, invite_url))


def _earn_details_text(referral_code: str, percent: int, total_earned: int) -> str:
    return (
        "آمار کسب درآمدت\n\n"
        f"کد دعوتت:\n{html_code(referral_code.upper())}\n\n"
        f"پورسانت فعلی: {percent}٪ از هر پرداخت\n"
        f"تا الان دراوردی: {total_earned:,} تومن\n\n"
        "فقط کسایی که مستقیم با لینک دعوت تو اومدن برات پورسانت می‌ذارن.\n"
        "بعد هر پرداخت موفق، سهمت خودکار میره کیف پولت."
    )


def _profile_text(user: User, subscription_count: int, earning_enabled: bool, referral_total: int = 0) -> str:
    role_label = "ادمین" if user.role == "admin" else "کاربر"
    lines = [
        "حساب کاربری",
        "",
        f"شناسه تلگرام: {user.telegram_id}",
        f"نقش: {role_label}",
        f"موجودی کیف پول: {user.wallet_balance:,} تومان",
        f"تعداد اشتراک‌ها: {subscription_count}",
    ]
    if earning_enabled:
        lines.extend(
            [
                "",
                f"درآمد ثبت‌شده: {referral_total:,} تومان",
                f"کد دعوت: {html_code(user.referral_code.upper())}",
            ]
        )
    return "\n".join(lines)


def _insufficient_wallet_text(wallet_balance: int, final_price: int) -> str:
    shortage = max(final_price - wallet_balance, 0)
    return (
        "موجودی کیف پول کافی نیست.\n\n"
        f"موجودی کیف پول شما: {wallet_balance:,} تومان\n"
        f"مبلغ پلن انتخابی: {final_price:,} تومان\n"
        f"مبلغ کسری: {shortage:,} تومان"
    )


def _parse_coupon_offer_suffix(parts: list[str]) -> tuple[int, int, str, int]:
    raw_duration, raw_gb, source, raw_discount = parts[2], parts[3], parts[4], parts[5]
    return int(raw_duration), int(raw_gb), source, int(raw_discount)


async def _show_purchase_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    repository: Repository,
    *,
    traffic_gb: int,
    duration_days: int,
    source: str,
    preset_discount: int,
    coupon_code_id: int = 0,
    coupon_percent: int = 0,
    coupon_code: str = "",
) -> None:
    settings = await repository.get_pricing_settings()
    offer = repository.build_offer(settings, traffic_gb, duration_days, source, preset_discount)
    final_offer = repository.apply_coupon_to_offer(offer, coupon_percent) if coupon_percent else offer
    await state.update_data(
        traffic_gb=traffic_gb,
        duration_days=duration_days,
        source=source,
        discount_percent=preset_discount,
        coupon_code_id=coupon_code_id,
        coupon_percent=coupon_percent,
        coupon_code=coupon_code,
    )
    await _edit_callback_message(
        callback,
        purchase_confirm_text(final_offer, coupon_percent=coupon_percent, coupon_code=coupon_code),
        reply_markup=confirm_purchase_keyboard(final_offer),
        parse_mode="HTML",
    )


def _build_purchase_offer_from_state(repository: Repository, data: dict, settings) -> tuple:
    traffic_gb = int(data["traffic_gb"])
    duration_days = int(data["duration_days"])
    source = str(data["source"])
    preset_discount = int(data["discount_percent"])
    coupon_percent = int(data.get("coupon_percent") or 0)
    offer = repository.build_offer(settings, traffic_gb, duration_days, source, preset_discount)
    if coupon_percent:
        offer = repository.apply_coupon_to_offer(offer, coupon_percent)
    return offer, int(data.get("coupon_code_id") or 0), str(data.get("coupon_code") or "")


async def _edit_callback_message(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def _subscription_detail_text(subscription: Subscription) -> str:
    return with_footer(
        "جزئیات اشتراک\n"
        f"نام کاربری: {html_code(subscription.marzban_username)}\n"
        f"وضعیت: {subscription.status}\n"
        f"حجم کل: {subscription.traffic_gb} GB\n"
        f"روزهای کل خریداری شده: {subscription.duration_days}\n"
        f"مبلغ کل پرداختی: {subscription.final_price:,} تومان\n"
        f"{_subscription_link_text(subscription.subscription_url)}"
    )


async def _show_subscription_detail(callback: CallbackQuery, subscription: Subscription) -> None:
    text = _subscription_detail_text(subscription)
    markup = subscription_detail_keyboard(subscription.id)
    kwargs = {"reply_markup": markup, "parse_mode": "HTML"}
    if callback.message.text:
        await _edit_callback_message(callback, text, **kwargs)
    else:
        await callback.message.answer(text, **kwargs)


@router.message(CommandStart())
async def start(message: Message, ctx: AppContext) -> None:
    referred_by = None
    referral_feedback = ""
    parts = (message.text or "").split(maxsplit=1)
    referral_code = normalize_referral_code(parts[1]) if len(parts) == 2 else ""
    async with ctx.database.session() as db:
        repository = Repository(db)
        earning_enabled = await repository.get_earning_enabled()
        referrer = await repository.get_user_by_referral_code(referral_code) if referral_code and earning_enabled else None
        existing_user = await repository.get_user_by_telegram_id(message.from_user.id)
        if referrer and referrer.telegram_id != message.from_user.id:
            referred_by = referrer.id
            if existing_user:
                if existing_user.referred_by:
                    referral_feedback = "کد رفرال قبلا برای حساب شما ثبت شده است."
                    referred_by = None
                elif await repository.set_referred_by_if_empty(existing_user.id, referrer.id):
                    referral_feedback = "کد رفرال با موفقیت برای حساب شما ثبت شد."
                    referred_by = None
                else:
                    referral_feedback = "کد رفرال قبلا برای حساب شما ثبت شده است."
                    referred_by = None
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids, referred_by=referred_by)
        if user.is_blocked and message.from_user.id not in ctx.settings.admin_ids:
            await message.answer(with_footer("حساب شما توسط ادمین مسدود شده است."), reply_markup=back_to_main_keyboard())
            return
        if referred_by:
            referral_feedback = "کد رفرال با موفقیت برای حساب شما ثبت شد."
    if referral_feedback:
        await message.answer(referral_feedback, reply_markup=back_to_main_keyboard())
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        keyboard = await main_menu_for_user(repository, user, ctx)
    await message.answer(
        with_footer("به ربات فروش VPN خوش آمدید."),
        reply_markup=keyboard,
    )


@router.message(F.text == "/id")
async def show_id(message: Message, ctx: AppContext) -> None:
    is_admin = message.from_user.id in ctx.settings.admin_ids
    await message.answer(
        f"Telegram ID: `{message.from_user.id}`\n"
        f"Admin: {'yes' if is_admin else 'no'}\n"
        f"Configured admins: `{', '.join(str(item) for item in sorted(ctx.settings.admin_ids))}`",
        parse_mode="Markdown",
        reply_markup=back_to_main_keyboard(),
    )


@router.message(F.text == c.BACK)
async def back(message: Message, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        keyboard = await main_menu_for_user(repository, user, ctx)
    await message.answer(with_footer("منوی اصلی"), reply_markup=keyboard)


@router.callback_query(F.data == "menu:home")
async def back_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        keyboard = await main_menu_for_user(repository, user, ctx)
    await _edit_callback_message(callback, with_footer("منوی اصلی"), reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(F.text == c.WALLET)
async def wallet(message: Message, state: FSMContext, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        support_username = await repository.get_support_username()
    await message.answer(
        with_footer(f"موجودی کیف پول: {user.wallet_balance:,} تومان\nمبلغ شارژ را انتخاب کنید:"),
        reply_markup=wallet_top_up_keyboard(support_username),
    )


@router.callback_query(F.data == "menu:wallet")
async def wallet_callback(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        support_username = await repository.get_support_username()
    await _edit_callback_message(
        callback,
        with_footer(f"موجودی کیف پول: {user.wallet_balance:,} تومان\nمبلغ شارژ را انتخاب کنید:"),
        reply_markup=wallet_top_up_keyboard(support_username),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:amount:"))
async def wallet_preset_amount(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    amount = int(callback.data.split(":")[2])
    async with ctx.database.session() as db:
        support_username = await Repository(db).get_support_username()
    await state.update_data(amount=amount)
    await state.set_state(WalletTopUp.screenshot)
    await _edit_callback_message(
        callback,
        f"{ctx.settings.payment_card_text}\n"
        f"{ctx.settings.support_text}\n\n"
        f"مبلغ شارژ: {amount:,} تومان\n"
        "پس از پرداخت، اسکرین‌شات را ارسال کنید.",
        reply_markup=wallet_payment_keyboard(support_username),
    )
    await callback.answer()


@router.callback_query(F.data == "wallet:manual")
async def wallet_manual_amount(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        support_username = await Repository(db).get_support_username()
    await state.set_state(WalletTopUp.amount)
    await _edit_callback_message(
        callback,
        f"مبلغ شارژ را از {MIN_WALLET_TOP_UP:,} تا {MAX_WALLET_TOP_UP:,} تومان وارد کنید.",
        reply_markup=wallet_payment_keyboard(support_username),
    )
    await callback.answer()


@router.message(WalletTopUp.amount)
async def wallet_amount(message: Message, state: FSMContext, ctx: AppContext) -> None:
    try:
        amount = int((message.text or "").replace(",", "").strip())
    except ValueError:
        await message.answer("لطفا مبلغ را فقط با عدد وارد کنید.", reply_markup=wallet_payment_keyboard())
        return
    if amount < MIN_WALLET_TOP_UP or amount > MAX_WALLET_TOP_UP:
        await message.answer(f"مبلغ شارژ باید بین {MIN_WALLET_TOP_UP:,} تا {MAX_WALLET_TOP_UP:,} تومان باشد.", reply_markup=wallet_payment_keyboard())
        return
    await state.update_data(amount=amount)
    await state.set_state(WalletTopUp.screenshot)
    async with ctx.database.session() as db:
        support_username = await Repository(db).get_support_username()
    await message.answer(
        f"{ctx.settings.payment_card_text}\n"
        f"{ctx.settings.support_text}\n\n"
        f"مبلغ شارژ: {amount:,} تومان\n"
        "پس از پرداخت، اسکرین‌شات را ارسال کنید.",
        reply_markup=wallet_payment_keyboard(support_username),
    )


@router.message(WalletTopUp.screenshot, F.photo)
async def wallet_screenshot(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    amount = int(data["amount"])
    photo_id = message.photo[-1].file_id
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        payment = await repository.create_payment(user.id, amount, photo_id)
    for admin_id in ctx.settings.admin_ids:
        await message.bot.send_photo(
            admin_id,
            photo_id,
            caption=with_footer(f"درخواست شارژ #{payment.id}\nکاربر: {message.from_user.id}\nمبلغ: {amount:,} تومان"),
            reply_markup=payment_review_keyboard(payment.id),
        )
    await state.clear()
    await message.answer("درخواست شارژ برای ادمین ارسال شد.", reply_markup=back_to_main_keyboard())


@router.message(WalletTopUp.screenshot)
async def wallet_screenshot_invalid(message: Message) -> None:
    await message.answer("لطفا اسکرین‌شات پرداخت را به صورت عکس ارسال کنید.", reply_markup=wallet_payment_keyboard())


@router.message(F.text == c.BUY_SUBSCRIPTION)
async def buy_subscription(message: Message, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        presets = await repository.list_traffic_presets()
        show_trial = await should_show_trial_button(repository, user.id)
    await message.answer(
        with_footer("حجم اشتراک را انتخاب کنید:"),
        reply_markup=traffic_presets_keyboard(presets, show_trial=show_trial),
    )


@router.callback_query(F.data == "menu:buy")
async def buy_subscription_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        presets = await repository.list_traffic_presets()
        show_trial = await should_show_trial_button(repository, user.id)
    await _edit_callback_message(
        callback,
        with_footer("حجم اشتراک را انتخاب کنید:"),
        reply_markup=traffic_presets_keyboard(presets, show_trial=show_trial),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("traffic:preset:"))
async def choose_preset_traffic(callback: CallbackQuery, ctx: AppContext) -> None:
    traffic_gb = int(callback.data.split(":")[2])
    async with ctx.database.session() as db:
        repository = Repository(db)
        preset = await repository.get_traffic_preset(traffic_gb)
        settings = await repository.get_pricing_settings()
    if not preset or not preset.active:
        await callback.answer("این حجم فعال نیست.", show_alert=True)
        return
    if not settings.one_month_enabled and not settings.three_month_enabled:
        await callback.answer("فعلا هیچ مدت زمانی فعال نیست.", show_alert=True)
        return
    await _edit_callback_message(
        callback,
        with_footer(f"حجم انتخابی: {traffic_gb} GB\nمدت اشتراک را انتخاب کنید:"),
        reply_markup=duration_keyboard(settings, traffic_gb, "preset", preset.discount_percent),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("extend_traffic:"))
async def extend_choose_traffic(callback: CallbackQuery, ctx: AppContext) -> None:
    _, raw_subscription_id, action, *rest = callback.data.split(":")
    subscription_id = int(raw_subscription_id)
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    traffic_gb = int(rest[0])
    async with ctx.database.session() as db:
        repository = Repository(db)
        preset = await repository.get_traffic_preset(traffic_gb)
        settings = await repository.get_pricing_settings()
    if not preset or not preset.active:
        await callback.answer("این حجم فعال نیست.", show_alert=True)
        return
    await _edit_callback_message(
        callback,
        with_footer(f"حجم تمدید: {traffic_gb} GB\nمدت تمدید را انتخاب کنید:"),
        reply_markup=duration_keyboard(settings, traffic_gb, "preset", preset.discount_percent, prefix=f"extend_duration:{subscription_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("duration:"))
async def choose_duration(callback: CallbackQuery, ctx: AppContext) -> None:
    _, raw_duration, raw_gb, source, raw_discount = callback.data.split(":")
    duration_days = int(raw_duration)
    traffic_gb = int(raw_gb)
    discount_percent = int(raw_discount)
    async with ctx.database.session() as db:
        repository = Repository(db)
        settings = await repository.get_pricing_settings()
        try:
            repository.build_offer(settings, traffic_gb, duration_days, source, discount_percent)
        except ValueError:
            await callback.answer("این انتخاب معتبر یا فعال نیست.", show_alert=True)
            return
    await _edit_callback_message(
        callback,
        with_footer(f"حجم انتخابی: {traffic_gb} GB\nمدت: {duration_days} روز\n\nکد تخفیف دارید؟"),
        reply_markup=purchase_coupon_keyboard(traffic_gb, duration_days, source, discount_percent),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("coupon:skip:"))
async def purchase_coupon_skip(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    duration_days, traffic_gb, source, preset_discount = _parse_coupon_offer_suffix(callback.data.split(":"))
    async with ctx.database.session() as db:
        repository = Repository(db)
        settings = await repository.get_pricing_settings()
        try:
            repository.build_offer(settings, traffic_gb, duration_days, source, preset_discount)
        except ValueError:
            await callback.answer("این انتخاب معتبر یا فعال نیست.", show_alert=True)
            return
        await _show_purchase_confirm(
            callback,
            state,
            repository,
            traffic_gb=traffic_gb,
            duration_days=duration_days,
            source=source,
            preset_discount=preset_discount,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("coupon:ask:"))
async def purchase_coupon_ask(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    duration_days, traffic_gb, source, preset_discount = _parse_coupon_offer_suffix(callback.data.split(":"))
    await state.update_data(
        traffic_gb=traffic_gb,
        duration_days=duration_days,
        source=source,
        discount_percent=preset_discount,
        coupon_code_id=0,
        coupon_percent=0,
        coupon_code="",
    )
    await state.set_state(PurchaseCoupon.code)
    await _edit_callback_message(
        callback,
        with_footer("کد تخفیف را ارسال کنید."),
        reply_markup=back_to_main_keyboard(),
    )
    await callback.answer()


@router.message(PurchaseCoupon.code)
async def purchase_coupon_entered(message: Message, state: FSMContext, ctx: AppContext) -> None:
    code = (message.text or "").strip()
    data = await state.get_data()
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        try:
            discount = await repository.validate_discount_for_user(code, user.id)
        except ValueError as exc:
            await message.answer(with_footer(discount_error_message(exc)), reply_markup=back_to_main_keyboard())
            return
        settings = await repository.get_pricing_settings()
        try:
            offer = repository.build_offer(
                settings,
                int(data["traffic_gb"]),
                int(data["duration_days"]),
                str(data["source"]),
                int(data["discount_percent"]),
            )
        except ValueError:
            await message.answer("این انتخاب معتبر یا فعال نیست.", reply_markup=back_to_main_keyboard())
            await state.clear()
            return
        final_offer = repository.apply_coupon_to_offer(offer, discount.discount_percent)
    await state.update_data(
        coupon_code_id=discount.id,
        coupon_percent=discount.discount_percent,
        coupon_code=discount.code,
    )
    await state.set_state(None)
    await message.answer(
        purchase_confirm_text(final_offer, coupon_percent=discount.discount_percent, coupon_code=discount.code),
        reply_markup=confirm_purchase_keyboard(final_offer),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("extend_duration:"))
async def extend_choose_duration(callback: CallbackQuery, ctx: AppContext) -> None:
    _, raw_subscription_id, raw_duration, raw_gb, source, raw_discount = callback.data.split(":")
    subscription_id = int(raw_subscription_id)
    duration_days = int(raw_duration)
    traffic_gb = int(raw_gb)
    discount_percent = int(raw_discount)
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        settings = await repository.get_pricing_settings()
        try:
            offer = repository.build_offer(settings, traffic_gb, duration_days, source, discount_percent)
        except ValueError:
            await callback.answer("این انتخاب معتبر یا فعال نیست.", show_alert=True)
            return
    await _edit_callback_message(
        callback,
        with_footer(
            "تایید تمدید\n"
            f"اشتراک: {subscription.marzban_username}\n"
            f"حجم اضافه: {offer.traffic_gb} GB\n"
            f"روز اضافه: {offer.duration_days}\n"
            f"مبلغ تمدید: {offer.final_price:,} تومان"
        ),
        reply_markup=confirm_extension_keyboard(subscription.id, offer),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("extend_confirm:"))
async def extend_confirm(callback: CallbackQuery, ctx: AppContext) -> None:
    _, raw_subscription_id, raw_gb, raw_duration, source, raw_discount = callback.data.split(":")
    subscription_id = int(raw_subscription_id)
    traffic_gb = int(raw_gb)
    duration_days = int(raw_duration)
    discount_percent = int(raw_discount)
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        subscription = await repository.get_user_subscription(user.id, subscription_id)
        settings = await repository.get_pricing_settings()
        if not subscription:
            await callback.answer("اشتراک پیدا نشد.", show_alert=True)
            return
        try:
            offer = repository.build_offer(settings, traffic_gb, duration_days, source, discount_percent)
        except ValueError:
            await callback.answer("این انتخاب معتبر یا فعال نیست.", show_alert=True)
            return
        if user.wallet_balance < offer.final_price:
            await _edit_callback_message(
                callback,
                with_footer(_insufficient_wallet_text(user.wallet_balance, offer.final_price)),
                reply_markup=subscription_detail_keyboard(subscription.id),
            )
            await callback.answer()
            return
        try:
            await ctx.quota.ensure_available(repository, requested_gb=offer.traffic_gb)
        except VolumeQuotaError:
            await callback.answer("ظرفیت فروش این ربات کافی نیست.", show_alert=True)
            return
    await _edit_callback_message(callback, "در حال تمدید اشتراک...", reply_markup=subscription_back_keyboard(subscription.id))
    try:
        marzban_sub = await ctx.marzban.extend_subscription(
            subscription.marzban_username,
            offer.traffic_gb,
            offer.duration_days,
            subscription.expires_at,
            subscription.traffic_gb,
        )
    except MarzbanError as exc:
        await _edit_callback_message(callback, f"تمدید ناموفق بود:\n{exc}", reply_markup=subscription_detail_keyboard(subscription.id))
        await callback.answer()
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        fresh_user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        fresh_subscription = await repository.get_user_subscription(fresh_user.id, subscription_id)
        if not fresh_subscription:
            await callback.answer("اشتراک پیدا نشد.", show_alert=True)
            return
        updated = await repository.extend_subscription_after_charge(fresh_user, fresh_subscription, offer, marzban_sub.expires_at)
        if marzban_sub.subscription_url:
            updated = await repository.update_subscription_url(updated.id, marzban_sub.subscription_url)
    await _edit_callback_message(
        callback,
        "اشتراک تمدید شد.\n"
        f"نام کاربری: {html_code(updated.marzban_username)}\n"
        f"حجم کل: {updated.traffic_gb} GB\n"
        f"روزهای کل خریداری شده: {updated.duration_days}\n"
        f"مبلغ کل پرداختی: {updated.final_price:,} تومان\n"
        f"{_subscription_link_text(updated.subscription_url)}",
        reply_markup=subscription_detail_keyboard(updated.id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:"))
async def confirm_purchase(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        settings = await repository.get_pricing_settings()
        try:
            offer, coupon_code_id, coupon_code = _build_purchase_offer_from_state(repository, data, settings)
        except (ValueError, KeyError):
            _, raw_gb, raw_duration, source, raw_discount = callback.data.split(":")
            try:
                offer = repository.build_offer(settings, int(raw_gb), int(raw_duration), source, int(raw_discount))
                coupon_code_id, coupon_code = 0, ""
            except ValueError:
                await callback.answer("این انتخاب معتبر یا فعال نیست.", show_alert=True)
                return
        if coupon_code_id and coupon_code:
            try:
                await repository.validate_discount_for_user(coupon_code, user.id)
            except ValueError as exc:
                await callback.answer(discount_error_message(exc), show_alert=True)
                return
        if user.wallet_balance < offer.final_price:
            await _edit_callback_message(
                callback,
                with_footer(_insufficient_wallet_text(user.wallet_balance, offer.final_price)),
                reply_markup=back_to_main_keyboard(),
            )
            await callback.answer()
            return
        try:
            await ctx.quota.ensure_available(repository, requested_gb=offer.traffic_gb)
        except VolumeQuotaError:
            await callback.answer("ظرفیت فروش این ربات کافی نیست.", show_alert=True)
            return

    await state.update_data(
        traffic_gb=offer.traffic_gb,
        duration_days=offer.duration_days,
        source=offer.source,
        discount_percent=int(data.get("discount_percent") or 0),
        coupon_code_id=coupon_code_id,
        coupon_percent=int(data.get("coupon_percent") or 0),
        coupon_code=coupon_code,
    )
    await state.set_state(PurchaseUsername.username)
    await _edit_callback_message(
        callback,
        "نام کاربری دلخواه اشتراک را وارد کنید.\n"
        "فقط حروف انگلیسی، عدد و _ مجاز است. ربات در انتها یک کد ۳ حرفی اضافه می‌کند.",
        reply_markup=back_to_main_keyboard(),
    )
    await callback.answer()


@router.message(PurchaseUsername.username)
async def purchase_username_received(message: Message, state: FSMContext, ctx: AppContext) -> None:
    requested_username = (message.text or "").strip()
    cleaned_username = re.sub(r"[^a-zA-Z0-9_]", "", requested_username).strip("_")
    if not cleaned_username:
        await message.answer("نام کاربری معتبر نیست. فقط حروف انگلیسی، عدد و _ وارد کنید.", reply_markup=back_to_main_keyboard())
        return
    data = await state.get_data()
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        settings = await repository.get_pricing_settings()
        try:
            offer, coupon_code_id, coupon_code = _build_purchase_offer_from_state(repository, data, settings)
        except (ValueError, KeyError):
            await message.answer("این انتخاب معتبر یا فعال نیست.", reply_markup=back_to_main_keyboard())
            await state.clear()
            return
        if coupon_code_id and coupon_code:
            try:
                await repository.validate_discount_for_user(coupon_code, user.id)
            except ValueError as exc:
                await message.answer(with_footer(discount_error_message(exc)), reply_markup=back_to_main_keyboard())
                await state.clear()
                return
        if user.wallet_balance < offer.final_price:
            await message.answer(with_footer(_insufficient_wallet_text(user.wallet_balance, offer.final_price)), reply_markup=back_to_main_keyboard())
            await state.clear()
            return
        try:
            await ctx.quota.ensure_available(repository, requested_gb=offer.traffic_gb)
        except VolumeQuotaError:
            await message.answer("ظرفیت فروش این ربات کافی نیست.", reply_markup=back_to_main_keyboard())
            await state.clear()
            return

    await message.answer("در حال ساخت اشتراک...", reply_markup=back_to_main_keyboard())
    try:
        marzban_sub = await ctx.marzban.create_subscription(offer, user, cleaned_username)
    except MarzbanError as exc:
        await message.answer(f"ساخت اشتراک ناموفق بود:\n{exc}", reply_markup=back_to_main_keyboard())
        await state.clear()
        return

    async with ctx.database.session() as db:
        repository = Repository(db)
        fresh_user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        try:
            subscription = await repository.create_subscription_after_charge(
                fresh_user,
                offer,
                marzban_sub.username,
                marzban_sub.subscription_url,
                marzban_sub.expires_at,
                coupon_code_id=coupon_code_id or None,
            )
        except ValueError as exc:
            if str(exc) == "coupon_redeem_failed":
                await message.answer(with_footer(discount_error_message(exc)), reply_markup=back_to_main_keyboard())
            else:
                await message.answer("خرید ناموفق بود.", reply_markup=back_to_main_keyboard())
            await state.clear()
            return
    await state.clear()
    await message.answer(
        "اشتراک ساخته شد.\n"
        f"نام کاربری: `{subscription.marzban_username}`\n"
        f"اعتبار تا: {subscription.expires_at}\n"
        f"حجم: {subscription.traffic_gb} GB\n"
        f"مدت: {subscription.duration_days} روز\n"
        f"مبلغ پرداختی: {subscription.final_price:,} تومان\n"
        f"لینک اشتراک:\n{subscription.subscription_url}",
        parse_mode="Markdown",
        reply_markup=subscription_detail_keyboard(subscription.id),
    )


@router.message(F.text == c.MY_SUBSCRIPTIONS)
async def my_subscriptions(message: Message, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        total = await repository.count_user_subscriptions(user.id)
        subscriptions = await repository.list_user_subscriptions_page(user.id, 1, SUBS_PER_PAGE)
    if not subscriptions:
        await message.answer("شما هنوز اشتراکی ندارید.", reply_markup=back_to_main_keyboard())
        return
    total_pages = max((total + SUBS_PER_PAGE - 1) // SUBS_PER_PAGE, 1)
    await message.answer(with_footer("اشتراک های من"), reply_markup=subscriptions_page_keyboard(subscriptions, 1, total_pages))


@router.callback_query(F.data == "menu:subs")
async def my_subscriptions_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    await send_subscriptions_page(callback, ctx, 1)


@router.callback_query(F.data.startswith("subs:page:"))
async def subscriptions_page_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    page = int(callback.data.split(":")[2])
    await send_subscriptions_page(callback, ctx, page)


async def send_subscriptions_page(callback: CallbackQuery, ctx: AppContext, page: int) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        total = await repository.count_user_subscriptions(user.id)
        total_pages = max((total + SUBS_PER_PAGE - 1) // SUBS_PER_PAGE, 1)
        page = min(max(page, 1), total_pages)
        subscriptions = await repository.list_user_subscriptions_page(user.id, page, SUBS_PER_PAGE)
    if not subscriptions:
        await _edit_callback_message(callback, "شما هنوز اشتراکی ندارید.", reply_markup=back_to_main_keyboard())
        await callback.answer()
        return
    await _edit_callback_message(callback, with_footer("اشتراک های من"), reply_markup=subscriptions_page_keyboard(subscriptions, page, total_pages))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:detail:"))
async def subscription_detail(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.split(":")[2])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    await _show_subscription_detail(callback, subscription)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^sub:configs:\d+$"))
async def subscription_configs_menu(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.rsplit(":", 1)[-1])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    await _edit_callback_message(
        callback,
        with_footer("نوع دریافت کانفیگ را انتخاب کنید."),
        reply_markup=subscription_configs_keyboard(subscription.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:link:"))
async def subscription_link(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.split(":")[2])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    await _edit_callback_message(
        callback,
        with_footer(_subscription_link_text(subscription.subscription_url)),
        reply_markup=subscription_detail_keyboard(subscription.id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:configs_link:"))
async def subscription_configs_link(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.split(":")[2])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    raw_text = await ctx.marzban.fetch_subscription_text(subscription.subscription_url)
    configs = parse_v2ray_configs(raw_text, subscription.subscription_url)
    for index, config in enumerate(configs, start=1):
        qr_file = BufferedInputFile(make_qr_png(config), filename=f"{subscription.marzban_username}_config_{index}.png")
        caption = with_footer(_config_text(index, config))
        if len(caption) <= TELEGRAM_PHOTO_CAPTION_LIMIT:
            await callback.message.answer_photo(qr_file, caption=caption, parse_mode="HTML", reply_markup=subscription_back_keyboard(subscription.id))
        else:
            await callback.message.answer_photo(qr_file, caption=with_footer(f"کانفیگ {index}"), reply_markup=subscription_back_keyboard(subscription.id))
            await callback.message.answer(with_footer(_config_text(index, config)), parse_mode="HTML", reply_markup=subscription_back_keyboard(subscription.id))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:configs_all:"))
async def subscription_configs_all(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.split(":")[2])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    raw_text = await ctx.marzban.fetch_subscription_text(subscription.subscription_url)
    configs = parse_v2ray_configs(raw_text, subscription.subscription_url)
    chunks = _configs_text_chunks(configs)
    await _edit_callback_message(
        callback,
        with_footer(chunks[0]),
        reply_markup=subscription_detail_keyboard(subscription.id),
        parse_mode="HTML",
    )
    for chunk in chunks[1:]:
        await callback.message.answer(with_footer(chunk), parse_mode="HTML", reply_markup=subscription_back_keyboard(subscription.id))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:qr:"))
async def subscription_qr(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.split(":")[2])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    qr_file = BufferedInputFile(make_qr_png(subscription.subscription_url), filename=f"{subscription.marzban_username}.png")
    await callback.message.answer_photo(qr_file, caption=with_footer(subscription.marzban_username), reply_markup=subscription_back_keyboard(subscription.id))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:configs_txt:"))
async def subscription_configs_txt(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.split(":")[2])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    raw_text = await ctx.marzban.fetch_subscription_text(subscription.subscription_url)
    configs = parse_v2ray_configs(raw_text, subscription.subscription_url)
    text = build_configs_txt(subscription.subscription_url, configs)
    txt_file = BufferedInputFile(text.encode("utf-8"), filename=f"{subscription.marzban_username}.txt")
    await callback.message.answer_document(txt_file, caption=with_footer("فایل متنی کانفیگ‌ها"), reply_markup=subscription_back_keyboard(subscription.id))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:revoke:"))
async def subscription_revoke(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.split(":")[2])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    try:
        new_url = await ctx.marzban.revoke_subscription(subscription.marzban_username)
    except MarzbanError as exc:
        await _edit_callback_message(callback, f"خطا در تغییر لینک اشتراک:\n{exc}", reply_markup=subscription_detail_keyboard(subscription.id))
        await callback.answer()
        return
    if new_url:
        async with ctx.database.session() as db:
            await Repository(db).update_subscription_url(subscription.id, new_url)
    await _edit_callback_message(
        callback,
        "لینک اشتراک تغییر کرد و لینک جدید ذخیره شد." if new_url else "درخواست تغییر لینک انجام شد.",
        reply_markup=subscription_detail_keyboard(subscription.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:extend:"))
async def subscription_extend_start(callback: CallbackQuery, ctx: AppContext) -> None:
    subscription_id = int(callback.data.split(":")[2])
    subscription = await get_owned_subscription(callback, ctx, subscription_id)
    if not subscription:
        return
    async with ctx.database.session() as db:
        presets = await Repository(db).list_traffic_presets()
    await _edit_callback_message(
        callback,
        with_footer("حجم تمدید را انتخاب کنید:"),
        reply_markup=traffic_presets_keyboard(presets, prefix=f"extend_traffic:{subscription.id}"),
    )
    await callback.answer()


async def get_owned_subscription(callback: CallbackQuery, ctx: AppContext, subscription_id: int):
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        subscription = await repository.get_user_subscription(user.id, subscription_id)
    if not subscription:
        await callback.answer("اشتراک پیدا نشد.", show_alert=True)
        return None
    return subscription


@router.message(F.text == c.PROFILE)
async def profile(message: Message, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        subscription_count = await repository.count_user_subscriptions(user.id)
        earning_enabled = await repository.get_earning_enabled()
        referral_total = await repository.get_referral_earnings_total(user.id) if earning_enabled else 0
        support_username = await repository.get_support_username()
    await message.answer(
        with_footer(_profile_text(user, subscription_count, earning_enabled, referral_total)),
        reply_markup=profile_keyboard(support_username, earning_enabled),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu:profile")
async def profile_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        subscription_count = await repository.count_user_subscriptions(user.id)
        earning_enabled = await repository.get_earning_enabled()
        referral_total = await repository.get_referral_earnings_total(user.id) if earning_enabled else 0
        support_username = await repository.get_support_username()
    await _edit_callback_message(
        callback,
        with_footer(_profile_text(user, subscription_count, earning_enabled, referral_total)),
        reply_markup=profile_keyboard(support_username, earning_enabled),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(F.text == c.TUTORIAL)
async def tutorial(message: Message, ctx: AppContext) -> None:
    await message.answer(
        with_footer(guides_home_text(extra_note=ctx.settings.tutorial_text)),
        reply_markup=guides_platforms_keyboard(),
    )


@router.callback_query(F.data == "menu:tutorial")
async def tutorial_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    await _edit_callback_message(
        callback,
        with_footer(guides_home_text(extra_note=ctx.settings.tutorial_text)),
        reply_markup=guides_platforms_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("guide:p:"))
async def guide_platform_callback(callback: CallbackQuery) -> None:
    platform_key = callback.data.removeprefix("guide:p:")
    platform = get_platform(platform_key)
    if platform is None:
        await callback.answer("سیستم‌عامل پیدا نشد.", show_alert=True)
        return
    await _edit_callback_message(
        callback,
        with_footer(guides_platform_text(platform)),
        reply_markup=guides_apps_keyboard(platform),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("guide:a:"))
async def guide_app_callback(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 4 or parts[0] != "guide" or parts[1] != "a":
        await callback.answer("درخواست نامعتبر.", show_alert=True)
        return
    platform_key, app_key = parts[2], parts[3]
    platform = get_platform(platform_key)
    if platform is None:
        await callback.answer("سیستم‌عامل پیدا نشد.", show_alert=True)
        return
    app = get_app(platform_key, app_key)
    if app is None:
        await callback.answer("اپ پیدا نشد.", show_alert=True)
        return
    await _edit_callback_message(
        callback,
        with_footer(guides_app_text(platform, app)),
        reply_markup=guides_app_keyboard(platform, app),
    )
    await callback.answer()


@router.message(F.text == c.EARN)
async def earn(message: Message, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(message.from_user, ctx.settings.admin_ids)
        earning_enabled = await repository.get_earning_enabled()
        earning_percent = await repository.get_earning_percent()
    if not earning_enabled:
        await message.answer(with_footer("بخش کسب درآمد در حال حاضر فعال نیست."), reply_markup=back_to_main_keyboard())
        return
    bot = await message.bot.me()
    bot_name = _bot_display_name(first_name=bot.first_name, username=bot.username)
    invite_url = _referral_invite_url(user.referral_code, bot.username)
    await _send_earn_invite(message, bot_name=bot_name, invite_url=invite_url, earning_percent=earning_percent)


@router.callback_query(F.data == "menu:earn")
async def earn_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        earning_enabled = await repository.get_earning_enabled()
        earning_percent = await repository.get_earning_percent()
    if not earning_enabled:
        await _edit_callback_message(callback, with_footer("بخش کسب درآمد در حال حاضر فعال نیست."), reply_markup=back_to_main_keyboard())
        await callback.answer()
        return
    bot = await callback.bot.me()
    bot_name = _bot_display_name(first_name=bot.first_name, username=bot.username)
    invite_url = _referral_invite_url(user.referral_code, bot.username)
    await _edit_callback_message(
        callback,
        with_footer(_earn_invite_instructions(earning_percent)),
        reply_markup=earn_keyboard(),
        parse_mode="HTML",
    )
    await callback.message.answer(_earn_share_message(bot_name, invite_url))
    await callback.answer()


@router.callback_query(F.data == "earn:details")
async def earn_details_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(callback.from_user, ctx.settings.admin_ids)
        earning_enabled = await repository.get_earning_enabled()
        percent = await repository.get_earning_percent()
        total_earned = await repository.get_referral_earnings_total(user.id)
    if not earning_enabled:
        await _edit_callback_message(callback, with_footer("بخش کسب درآمد در حال حاضر فعال نیست."), reply_markup=back_to_main_keyboard())
        await callback.answer()
        return
    await _edit_callback_message(
        callback,
        with_footer(_earn_details_text(user.referral_code, percent, total_earned)),
        reply_markup=earn_details_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
