from __future__ import annotations

from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import constants as c
from bot.db import Subscription, User

USERS_PER_PAGE = 8
WALLET_QUICK_AMOUNTS = (50_000, 100_000, 250_000, 500_000)


def users_total_pages(total_users: int) -> int:
    return max(1, ceil(total_users / USERS_PER_PAGE))


def users_list_text(*, users: list[User], page: int, total_users: int, search_query: str | None = None) -> str:
    total_pages = users_total_pages(total_users)
    lines = ["مدیریت کاربران", ""]
    if search_query:
        lines.extend([f"جستجو: {search_query}", f"نتایج: {total_users}", ""])
    else:
        lines.extend([f"تعداد کل: {total_users}", f"صفحه {page} از {total_pages}", ""])
    lines.append("روی هر کاربر بزنید تا جزئیات و عملیات را ببینید.")
    return "\n".join(lines)


def user_detail_text(*, user: User, subscription_count: int) -> str:
    status = "مسدود" if user.is_blocked else "فعال"
    role = "ادمین" if user.role == "admin" else "کاربر"
    lines = [
        "جزئیات کاربر",
        "",
        f"شناسه تلگرام: {user.telegram_id}",
        f"نقش: {role}",
        f"وضعیت: {status}",
        f"کیف پول: {user.wallet_balance:,} تومان",
        f"کد دعوت: {user.referral_code.upper()}",
        f"تعداد اشتراک: {subscription_count}",
    ]
    if user.referred_by:
        lines.append(f"دعوت‌شده توسط user_id: {user.referred_by}")
    return "\n".join(lines)


def user_subscriptions_text(*, user: User, subscriptions: list[Subscription]) -> str:
    lines = [f"اشتراک‌های {user.telegram_id}", ""]
    if not subscriptions:
        lines.append("اشتراکی ثبت نشده است.")
        return "\n".join(lines)
    for sub in subscriptions[:15]:
        lines.append(f"• {sub.marzban_username} | {sub.status} | {sub.traffic_gb}GB | {sub.duration_days}روز")
    if len(subscriptions) > 15:
        lines.append(f"... و {len(subscriptions) - 15} مورد دیگر")
    return "\n".join(lines)


def _user_button_label(user: User) -> str:
    status = "🚫" if user.is_blocked else "✅"
    role = "👑" if user.role == "admin" else "👤"
    return f"{status}{role} {user.telegram_id} · {user.wallet_balance:,}"


def admin_users_list_keyboard(
    *,
    users: list[User],
    page: int,
    total_users: int,
    search_query: str | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🔎 جستجو", callback_data="adm:users:search")],
    ]
    for user in users:
        rows.append([InlineKeyboardButton(text=_user_button_label(user), callback_data=f"adm:user:{user.id}")])
    total_pages = users_total_pages(total_users)
    if total_pages > 1:
        prev_page = max(page - 1, 1)
        next_page = min(page + 1, total_pages)
        rows.append(
            [
                InlineKeyboardButton(text="◀️", callback_data=f"adm:users:page:{prev_page}"),
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
                InlineKeyboardButton(text="▶️", callback_data=f"adm:users:page:{next_page}"),
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
                InlineKeyboardButton(text="✉️ پیام به کاربر", callback_data=f"adm:user:{user.id}:message"),
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
