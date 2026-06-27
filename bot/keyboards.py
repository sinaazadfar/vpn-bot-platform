from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot import constants as c
from bot.admin_users import subscription_status_emoji
from bot.db import PricingSettings, PurchaseOffer, Subscription, TrafficPreset

WALLET_TOP_UP_AMOUNTS = (100_000, 250_000, 500_000, 1_000_000)
MIN_WALLET_TOP_UP = 50_000
MAX_WALLET_TOP_UP = 3_000_000


def main_menu(is_admin: bool, web_app_url: str = "", support_username: str = "", earning_enabled: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=c.BUY_SUBSCRIPTION, callback_data="menu:buy")],
        [
            InlineKeyboardButton(text=c.WALLET, callback_data="menu:wallet"),
            InlineKeyboardButton(text=c.PROFILE, callback_data="menu:profile"),
        ],
        [InlineKeyboardButton(text=c.MY_SUBSCRIPTIONS, callback_data="menu:subs")],
    ]
    if earning_enabled:
        rows.append(
            [
                InlineKeyboardButton(text=c.EARN, callback_data="menu:earn"),
                InlineKeyboardButton(text=c.TUTORIAL, callback_data="menu:tutorial"),
            ]
        )
    else:
        rows.append([InlineKeyboardButton(text=c.TUTORIAL, callback_data="menu:tutorial")])
    rows.append(
        [
            InlineKeyboardButton(text=c.SUPPORT, callback_data="menu:support"),
            InlineKeyboardButton(text="تیکت", callback_data="menu:tickets"),
        ]
    )
    if is_admin:
        rows.append([InlineKeyboardButton(text=c.ADMIN_PANEL, callback_data="admin:panel")])
    if web_app_url:
        rows.append([InlineKeyboardButton(text="وب اپ", web_app=WebAppInfo(url=web_app_url))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=c.ADMIN_PAYMENTS, callback_data="admin:payments"),
                InlineKeyboardButton(text="تیکت‌ها", callback_data="admin:tickets"),
            ],
            [
                InlineKeyboardButton(text=c.ADMIN_USERS, callback_data="admin:users"),
                InlineKeyboardButton(text="گزارش فروش", callback_data="admin:sales"),
            ],
            [
                InlineKeyboardButton(text=c.ADMIN_PLANS, callback_data="admin:plans"),
                InlineKeyboardButton(text=c.ADMIN_QUOTA, callback_data="admin:quota"),
            ],
            [
                InlineKeyboardButton(text="تنظیمات پیشرفته", callback_data="admin:settings"),
                InlineKeyboardButton(text=c.ADMIN_BROADCAST, callback_data="admin:broadcast"),
            ],
            [
                InlineKeyboardButton(text="تنظیم پشتیبانی", callback_data="admin:support"),
                InlineKeyboardButton(text="تنظیمات کسب درآمد", callback_data="admin:earning"),
            ],
            [InlineKeyboardButton(text=c.BACK, callback_data="menu:home")],
        ],
    )


def admin_earning_keyboard(enabled: bool, percent: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"وضعیت: {'فعال' if enabled else 'غیرفعال'}", callback_data="earning:toggle")],
            [InlineKeyboardButton(text=f"پورسانت: {percent}٪", callback_data="earning:set_percent")],
            [InlineKeyboardButton(text=c.BACK, callback_data="admin:panel")],
        ]
    )


def _support_button(support_username: str = "") -> InlineKeyboardButton:
    return (
        InlineKeyboardButton(text=c.SUPPORT, url=f"https://t.me/{support_username}")
        if support_username
        else InlineKeyboardButton(text=c.SUPPORT, callback_data="menu:support")
    )


def wallet_top_up_keyboard(support_username: str = "") -> InlineKeyboardMarkup:
    amount_buttons = [
        InlineKeyboardButton(text=f"{amount:,} تومان", callback_data=f"wallet:amount:{amount}")
        for amount in WALLET_TOP_UP_AMOUNTS
    ]
    rows = [amount_buttons[index:index + 2] for index in range(0, len(amount_buttons), 2)]
    rows.append([InlineKeyboardButton(text="مبلغ دلخواه", callback_data="wallet:manual")])
    rows.append([InlineKeyboardButton(text="تاریخچه تراکنش‌ها", callback_data="wallet:ledger:1")])
    rows.append([InlineKeyboardButton(text=c.BACK, callback_data="menu:home"), _support_button(support_username)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wallet_payment_keyboard(support_username: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c.BACK, callback_data="menu:wallet"), _support_button(support_username)],
        ]
    )


def wallet_after_approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c.WALLET, callback_data="menu:wallet")],
            [InlineKeyboardButton(text=c.BACK, callback_data="menu:home")],
        ]
    )


def earn_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="جزئیات درآمد", callback_data="earn:details")],
            [InlineKeyboardButton(text=c.BACK, callback_data="menu:home")],
        ]
    )


def earn_details_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="لینک دعوت من", callback_data="menu:earn")],
            [InlineKeyboardButton(text=c.BACK, callback_data="menu:home")],
        ]
    )


def profile_keyboard(support_username: str = "", earning_enabled: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=c.WALLET, callback_data="menu:wallet"),
            InlineKeyboardButton(text=c.MY_SUBSCRIPTIONS, callback_data="menu:subs"),
        ],
    ]
    if earning_enabled:
        rows.append([InlineKeyboardButton(text=c.EARN, callback_data="menu:earn")])
    rows.append(
        [
            InlineKeyboardButton(text=c.SUPPORT, callback_data="menu:support"),
            InlineKeyboardButton(text="تیکت", callback_data="menu:tickets"),
        ]
    )
    rows.append([InlineKeyboardButton(text=c.BACK, callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c.BACK, callback_data="menu:home")]])


def wallet_ledger_keyboard(*, page: int, total_pages: int, scope: str, scope_id: int = 0) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        prev_page = max(page - 1, 1)
        next_page = min(page + 1, total_pages)
        if scope == "adm":
            prev_cb = f"adm:user:{scope_id}:ledger:page:{prev_page}"
            next_cb = f"adm:user:{scope_id}:ledger:page:{next_page}"
        else:
            prev_cb = f"wallet:ledger:{prev_page}"
            next_cb = f"wallet:ledger:{next_page}"
        rows.append(
            [
                InlineKeyboardButton(text="◀️", callback_data=prev_cb),
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
                InlineKeyboardButton(text="▶️", callback_data=next_cb),
            ]
        )
    back_callback = f"adm:user:{scope_id}" if scope == "adm" else "menu:wallet"
    rows.append([InlineKeyboardButton(text=c.BACK, callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c.BACK, callback_data="admin:panel")]])


def admin_discount_max_uses_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="♾️ نامحدود", callback_data="discount:max_uses:0")],
            [InlineKeyboardButton(text=c.BACK, callback_data="admin:panel")],
        ]
    )


def admin_discount_valid_days_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="♾️ نامحدود", callback_data="discount:valid_days:0")],
            [InlineKeyboardButton(text=c.BACK, callback_data="admin:panel")],
        ]
    )


def subscription_back_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c.BACK, callback_data=f"sub:detail:{subscription_id}")]])


def traffic_presets_keyboard(
    presets: list[TrafficPreset],
    prefix: str = "traffic",
    *,
    show_trial: bool = False,
) -> InlineKeyboardMarkup:
    preset_buttons = []
    for preset in presets:
        if not preset.active:
            continue
        text = f"{preset.gb} GB"
        if preset.discount_percent:
            text += f" - {preset.discount_percent}٪ تخفیف"
        preset_buttons.append(InlineKeyboardButton(text=text, callback_data=f"{prefix}:preset:{preset.gb}"))
    buttons = [preset_buttons[index:index + 2] for index in range(0, len(preset_buttons), 2)]
    if show_trial:
        buttons.insert(0, [InlineKeyboardButton(text="🎁 تست رایگان", callback_data="menu:trial")])
    buttons.append([InlineKeyboardButton(text=c.BACK, callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def duration_keyboard(settings: PricingSettings, traffic_gb: int, source: str, discount_percent: int, prefix: str = "duration") -> InlineKeyboardMarkup:
    buttons = []
    suffix = f"{traffic_gb}:{source}:{discount_percent}"
    if settings.one_month_enabled:
        buttons.append([InlineKeyboardButton(text="یک ماهه", callback_data=f"{prefix}:30:{suffix}")])
    if settings.three_month_enabled:
        buttons.append([InlineKeyboardButton(text=f"سه ماهه + {settings.three_month_extra_price:,} تومان", callback_data=f"{prefix}:90:{suffix}")])
    buttons.append([InlineKeyboardButton(text=c.BACK, callback_data="menu:buy")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def purchase_coupon_keyboard(traffic_gb: int, duration_days: int, source: str, discount_percent: int) -> InlineKeyboardMarkup:
    suffix = f"{duration_days}:{traffic_gb}:{source}:{discount_percent}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 کد تخفیف دارم", callback_data=f"coupon:ask:{suffix}")],
            [InlineKeyboardButton(text="ادامه بدون کد تخفیف", callback_data=f"coupon:skip:{suffix}")],
            [InlineKeyboardButton(text=c.BACK, callback_data="menu:buy")],
        ]
    )


def confirm_purchase_keyboard(offer: PurchaseOffer) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"خرید با {offer.final_price:,} تومان", callback_data=f"confirm:{offer.traffic_gb}:{offer.duration_days}:{offer.source}:{offer.discount_percent}")],
            [InlineKeyboardButton(text=c.BACK, callback_data="menu:buy")],
        ]
    )


def confirm_extension_keyboard(subscription_id: int, offer: PurchaseOffer) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"تمدید با {offer.final_price:,} تومان", callback_data=f"extend_confirm:{subscription_id}:{offer.traffic_gb}:{offer.duration_days}:{offer.source}:{offer.discount_percent}")],
            [InlineKeyboardButton(text=c.BACK, callback_data=f"sub:detail:{subscription_id}")],
        ]
    )


def _subscription_list_button_label(sub: Subscription) -> str:
    emoji = subscription_status_emoji(sub.status)
    text = f"{emoji} {sub.marzban_username} · {sub.traffic_gb}GB · {sub.duration_days} روز"
    return text if len(text) <= 64 else f"{text[:61]}…"


def subscriptions_page_keyboard(subscriptions: list[Subscription], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=_subscription_list_button_label(sub), callback_data=f"sub:detail:{sub.id}")]
        for sub in subscriptions
    ]
    rows.append([InlineKeyboardButton(text="🔎 جستجو", switch_inline_query_current_chat="subs:")])
    prev_page = max(page - 1, 1)
    next_page = min(page + 1, total_pages)
    rows.append(
        [
            InlineKeyboardButton(text="◀️", callback_data=f"subs:page:{prev_page}"),
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"subs:page:{next_page}"),
        ]
    )
    rows.append([InlineKeyboardButton(text=c.BACK, callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_configs_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="کانفیگ‌ها با QR", callback_data=f"sub:configs_link:{subscription_id}")],
            [InlineKeyboardButton(text="همه کانفیگ‌ها", callback_data=f"sub:configs_all:{subscription_id}")],
            [InlineKeyboardButton(text="فایل متنی کانفیگ‌ها", callback_data=f"sub:configs_txt:{subscription_id}")],
            [InlineKeyboardButton(text=c.BACK, callback_data=f"sub:detail:{subscription_id}")],
        ]
    )


def subscription_detail_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="QR اشتراک", callback_data=f"sub:qr:{subscription_id}"),
                InlineKeyboardButton(text="لینک اشتراک", callback_data=f"sub:link:{subscription_id}"),
            ],
            [InlineKeyboardButton(text="دریافت کانفیگ‌ها", callback_data=f"sub:configs:{subscription_id}")],
            [
                InlineKeyboardButton(text="تمدید اشتراک", callback_data=f"sub:extend:{subscription_id}"),
                InlineKeyboardButton(text="تغییر لینک اشتراک", callback_data=f"sub:revoke:{subscription_id}"),
            ],
            [InlineKeyboardButton(text="آموزش اتصال", callback_data="menu:tutorial")],
            [InlineKeyboardButton(text=c.BACK, callback_data="subs:page:1")],
        ]
    )


def admin_pricing_keyboard(settings: PricingSettings, presets: list[TrafficPreset]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"قیمت هر گیگ: {settings.per_gb_price:,}", callback_data="pricing:set_per_gb")],
        [InlineKeyboardButton(text=f"هزینه سه ماهه: {settings.three_month_extra_price:,}", callback_data="pricing:set_3m")],
        [
            InlineKeyboardButton(text=f"یک ماهه: {'فعال' if settings.one_month_enabled else 'غیرفعال'}", callback_data="pricing:toggle_1m"),
            InlineKeyboardButton(text=f"سه ماهه: {'فعال' if settings.three_month_enabled else 'غیرفعال'}", callback_data="pricing:toggle_3m"),
        ],
    ]
    preset_buttons = [
        InlineKeyboardButton(text=f"{preset.gb}GB تخفیف: {preset.discount_percent}٪", callback_data=f"pricing:preset:{preset.gb}")
        for preset in presets
    ]
    buttons.extend(preset_buttons[index:index + 2] for index in range(0, len(preset_buttons), 2))
    buttons.append([InlineKeyboardButton(text=c.BACK, callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_review_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="تایید", callback_data=f"pay_ok:{payment_id}"),
                InlineKeyboardButton(text="رد", callback_data=f"pay_no:{payment_id}"),
            ],
            [InlineKeyboardButton(text=c.BACK, callback_data="admin:payments")],
        ]
    )
