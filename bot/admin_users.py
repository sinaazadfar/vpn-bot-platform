from __future__ import annotations

from datetime import UTC, datetime
from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import constants as c
from bot.db import Subscription, User
from bot.marzban import MarzbanUserStats

USERS_PER_PAGE = 8
SUBS_PER_PAGE = 8
WALLET_QUICK_AMOUNTS = (50_000, 100_000, 250_000, 500_000)


def subscription_status_emoji(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"active", "فعال"}:
        return "🟢"
    if normalized in {"expired", "منقضی"}:
        return "🔴"
    if normalized in {"disabled", "غیرفعال"}:
        return "⚫"
    if normalized in {"limited"}:
        return "🟠"
    return "⚪"


def subscriptions_total_pages(total_subscriptions: int) -> int:
    return max(1, ceil(total_subscriptions / SUBS_PER_PAGE))


def format_expire_display(*, expire_ts: int | None = None, expires_at: str | None = None) -> str:
    if expire_ts:
        return datetime.fromtimestamp(expire_ts, UTC).strftime("%Y/%m/%d %H:%M")
    if expires_at:
        try:
            parsed = datetime.fromisoformat(expires_at)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).strftime("%Y/%m/%d %H:%M")
        except ValueError:
            return expires_at[:16]
    return "—"


def format_traffic_usage_block(*, usage: MarzbanUserStats | None, fallback_total_gb: int) -> list[str]:
    if usage and usage.data_limit > 0:
        remaining = max(usage.data_limit - usage.used_traffic, 0)
        used_gb = usage.used_traffic / (1024**3)
        limit_gb = usage.data_limit / (1024**3)
        remaining_gb = remaining / (1024**3)
        percent = min(100, int(usage.used_traffic * 100 / usage.data_limit))
        return [
            f"📊 مصرف: {used_gb:.2f} / {limit_gb:.1f} GB ({percent}%)",
            f"💾 باقی‌مانده: {remaining_gb:.2f} GB",
        ]
    return [f"📦 حجم ثبت‌شده: {fallback_total_gb} GB"]


def user_full_name(user: User) -> str:
    parts: list[str] = []
    if user.first_name:
        parts.append(user.first_name.strip())
    if user.last_name:
        parts.append(user.last_name.strip())
    return " ".join(parts).strip()


def user_display_name(user: User) -> str:
    name = user_full_name(user)
    if user.username:
        handle = f"@{user.username}"
        return f"{name} · {handle}" if name else handle
    if name:
        return name
    return str(user.telegram_id)


def user_button_title(user: User) -> str:
    name = user_full_name(user)
    if name:
        return name
    if user.username:
        return f"@{user.username}"
    return str(user.telegram_id)


def user_username_line(user: User) -> str | None:
    if user.username:
        return f"@{user.username}"
    return None


def users_total_pages(total_users: int) -> int:
    return max(1, ceil(total_users / USERS_PER_PAGE))


def users_list_text(*, users: list[User], page: int, total_users: int, search_query: str | None = None) -> str:
    total_pages = users_total_pages(total_users)
    lines = ["مدیریت کاربران", ""]
    if search_query:
        lines.extend([f"جستجو: {search_query}", f"نتایج: {total_users}", ""])
    else:
        lines.extend([f"تعداد کل: {total_users}", f"صفحه {page} از {total_pages}", ""])
    lines.append("برای جستجو: نام، یوزرنیم، آیدی تلگرام یا نام کاربری Marzban.")
    return "\n".join(lines)


def user_detail_text(*, user: User, subscription_count: int) -> str:
    status = "🚫 مسدود" if user.is_blocked else "✅ فعال"
    role = "👑 ادمین" if user.role == "admin" else "👤 کاربر"
    lines = [
        "جزئیات کاربر",
        "",
        f"نام: {user_full_name(user) or '—'}",
    ]
    username_line = user_username_line(user)
    if username_line:
        lines.append(f"یوزرنیم: {username_line}")
    lines.extend(
        [
            f"شناسه تلگرام: {user.telegram_id}",
            f"نقش: {role}",
            f"وضعیت: {status}",
            f"کیف پول: 💰 {user.wallet_balance:,} تومان",
            f"کد دعوت: {user.referral_code.upper()}",
            f"تعداد اشتراک: 📋 {subscription_count}",
        ]
    )
    if user.referred_by:
        lines.append(f"دعوت‌شده توسط user_id: {user.referred_by}")
    return "\n".join(lines)


def user_subscriptions_list_text(*, user: User, page: int, total_subscriptions: int) -> str:
    total_pages = subscriptions_total_pages(total_subscriptions)
    lines = [
        f"📋 اشتراک‌های {user_display_name(user)}",
        "",
        f"تعداد: {total_subscriptions} · صفحه {page} از {total_pages}",
        "",
        "روی هر اشتراک بزن تا جزئیات و حجم باقی‌مانده رو ببینی.",
    ]
    return "\n".join(lines)


def admin_subscription_detail_text(
    *,
    user: User,
    subscription: Subscription,
    usage: MarzbanUserStats | None,
) -> str:
    status = usage.status if usage else subscription.status
    emoji = subscription_status_emoji(status)
    lines = [
        f"{emoji} جزئیات اشتراک",
        "",
        f"👤 کاربر: {user_display_name(user)}",
        f"🔑 نام کاربری: {subscription.marzban_username}",
        f"📌 وضعیت: {emoji} {status}",
        "",
        *format_traffic_usage_block(usage=usage, fallback_total_gb=subscription.traffic_gb),
        f"⏳ انقضا: {format_expire_display(expire_ts=usage.expire if usage else None, expires_at=subscription.expires_at)}",
        f"📅 مدت خریداری‌شده: {subscription.duration_days} روز",
        f"💳 مبلغ پرداختی: {subscription.final_price:,} تومان",
    ]
    if usage is None:
        lines.extend(["", "⚠️ آمار لحظه‌ای Marzban در دسترس نبود."])
    return "\n".join(lines)


def _subscription_button_label(sub: Subscription) -> str:
    emoji = subscription_status_emoji(sub.status)
    text = f"{emoji} {sub.marzban_username} · {sub.traffic_gb}GB"
    return text if len(text) <= 64 else f"{text[:61]}…"


def admin_user_subscriptions_keyboard(*, user_id: int, subscriptions: list[Subscription], page: int, total_subscriptions: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sub in subscriptions:
        rows.append(
            [InlineKeyboardButton(text=_subscription_button_label(sub), callback_data=f"adm:user:{user_id}:sub:{sub.id}")]
        )
    total_pages = subscriptions_total_pages(total_subscriptions)
    if total_pages > 1:
        prev_page = max(page - 1, 1)
        next_page = min(page + 1, total_pages)
        rows.append(
            [
                InlineKeyboardButton(text="◀️", callback_data=f"adm:user:{user_id}:subs:page:{prev_page}"),
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
                InlineKeyboardButton(text="▶️", callback_data=f"adm:user:{user_id}:subs:page:{next_page}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به کاربر", callback_data=f"adm:user:{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_subscription_detail_keyboard(*, user_id: int, subscription_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 به‌روزرسانی آمار", callback_data=f"adm:user:{user_id}:sub:{subscription_id}")],
            [InlineKeyboardButton(text="🔙 لیست اشتراک‌ها", callback_data=f"adm:user:{user_id}:subs:page:1")],
            [InlineKeyboardButton(text="👤 جزئیات کاربر", callback_data=f"adm:user:{user_id}")],
        ]
    )


def user_subscriptions_text(*, user: User, subscriptions: list[Subscription]) -> str:
    lines = [f"اشتراک‌های {user_display_name(user)}", ""]
    if not subscriptions:
        lines.append("اشتراکی ثبت نشده است.")
        return "\n".join(lines)
    for sub in subscriptions[:15]:
        emoji = subscription_status_emoji(sub.status)
        lines.append(f"• {emoji} {sub.marzban_username} | {sub.traffic_gb}GB | {sub.duration_days}روز")
    if len(subscriptions) > 15:
        lines.append(f"... و {len(subscriptions) - 15} مورد دیگر")
    return "\n".join(lines)


def _user_button_label(user: User) -> str:
    status = "🚫" if user.is_blocked else "✅"
    role = "👑" if user.role == "admin" else "👤"
    text = f"{status}{role} {user_button_title(user)} · {user.wallet_balance:,}"
    return text if len(text) <= 64 else f"{text[:61]}…"


def admin_users_list_keyboard(
    *,
    users: list[User],
    page: int,
    total_users: int,
    search_query: str | None = None,
    filter_type: str = "all",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="همه", callback_data="adm:users:filter:all:1"),
            InlineKeyboardButton(text="مسدود", callback_data="adm:users:filter:blocked:1"),
        ],
        [
            InlineKeyboardButton(text="موجودی‌دار", callback_data="adm:users:filter:funded:1"),
            InlineKeyboardButton(text="دارای اشتراک", callback_data="adm:users:filter:with_subs:1"),
        ],
        [
            InlineKeyboardButton(text="🔎 جستجو", callback_data="adm:users:search"),
            InlineKeyboardButton(text="🔄 نام‌ها", callback_data="adm:users:sync"),
        ],
    ]
    for user in users:
        rows.append([InlineKeyboardButton(text=_user_button_label(user), callback_data=f"adm:user:{user.id}")])
    total_pages = users_total_pages(total_users)
    if total_pages > 1:
        prev_page = max(page - 1, 1)
        next_page = min(page + 1, total_pages)
        if search_query:
            page_cb = f"adm:users:search:page:{next_page}"
            prev_cb = f"adm:users:search:page:{prev_page}"
        elif filter_type != "all":
            page_cb = f"adm:users:filter:{filter_type}:{next_page}"
            prev_cb = f"adm:users:filter:{filter_type}:{prev_page}"
        else:
            page_cb = f"adm:users:page:{next_page}"
            prev_cb = f"adm:users:page:{prev_page}"
        rows.append(
            [
                InlineKeyboardButton(text="◀️", callback_data=prev_cb),
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
                InlineKeyboardButton(text="▶️", callback_data=page_cb),
            ]
        )
    if search_query:
        rows.append([InlineKeyboardButton(text="پاک کردن جستجو", callback_data="adm:users:page:1")])
    rows.append([InlineKeyboardButton(text=c.BACK, callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_detail_keyboard(*, user: User) -> InlineKeyboardMarkup:
    ban_label = "آزادسازی کاربر" if user.is_blocked else "مسدود کردن"
    ban_action = "unban" if user.is_blocked else "ban"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ شارژ کیف پول", callback_data=f"adm:user:{user.id}:wallet"),
                InlineKeyboardButton(text="📋 اشتراک‌ها", callback_data=f"adm:user:{user.id}:subs"),
            ],
            [
                InlineKeyboardButton(text="📒 تاریخچه کیف پول", callback_data=f"adm:user:{user.id}:ledger"),
                InlineKeyboardButton(text="✉️ پیام", callback_data=f"adm:user:{user.id}:message"),
            ],
            [
                InlineKeyboardButton(text=f"{'🔓' if user.is_blocked else '🔒'} {ban_label}", callback_data=f"adm:user:{user.id}:{ban_action}"),
            ],
            [
                InlineKeyboardButton(text="🔙 لیست کاربران", callback_data="adm:users:page:1"),
                InlineKeyboardButton(text=c.BACK, callback_data="admin:panel"),
            ],
        ]
    )


def admin_user_wallet_keyboard(user_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text=f"+{amount:,} تومان", callback_data=f"adm:wallet:{user_id}:{amount}")
            for amount in WALLET_QUICK_AMOUNTS[:2]
        ],
        [
            InlineKeyboardButton(text=f"+{amount:,} تومان", callback_data=f"adm:wallet:{user_id}:{amount}")
            for amount in WALLET_QUICK_AMOUNTS[2:]
        ],
        [InlineKeyboardButton(text="مبلغ دلخواه", callback_data=f"adm:wallet:{user_id}:custom")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm:user:{user_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wallet_admin_adjustment_user_text(*, amount: int, balance: int) -> str:
    if amount > 0:
        return "\n".join(
            [
                "💳 <b>شارژ کیف پول</b>",
                "",
                f"✅ مبلغ <b>{amount:,}</b> تومان به کیف پول شما اضافه شد.",
                "",
                "می‌توانید همین حالا اشتراک بخرید یا موجودی را در بخش کیف پول ببینید.",
                "",
                f"💰 موجودی فعلی: <b>{balance:,}</b> تومان",
            ]
        )
    abs_amount = abs(amount)
    return "\n".join(
        [
            "💳 <b>به‌روزرسانی کیف پول</b>",
            "",
            f"مبلغ <b>{abs_amount:,}</b> تومان از کیف پول شما کسر شد.",
            "",
            f"💰 موجودی فعلی: <b>{balance:,}</b> تومان",
        ]
    )


async def notify_wallet_admin_adjustment(bot, user: User, *, amount: int) -> bool:
    from bot.formatting import with_footer
    from bot.keyboards import back_to_main_keyboard, wallet_after_approval_keyboard

    if amount == 0:
        return False
    text = with_footer(wallet_admin_adjustment_user_text(amount=amount, balance=user.wallet_balance))
    keyboard = wallet_after_approval_keyboard() if amount > 0 else back_to_main_keyboard()
    try:
        await bot.send_message(user.telegram_id, text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        return False
    return True
