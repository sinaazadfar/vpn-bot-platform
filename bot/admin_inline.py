from __future__ import annotations

from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from bot.admin_users import user_display_name
from bot.db import User

INLINE_RESULTS_LIMIT = 20


def inline_user_share_text(user: User, *, subscription_count: int) -> str:
    status = "🚫 مسدود" if user.is_blocked else "✅ فعال"
    role = "👑 ادمین" if user.role == "admin" else "👤 کاربر"
    lines = [
        f"👤 {user_display_name(user)}",
        f"🆔 شناسه تلگرام: {user.telegram_id}",
        f"📌 وضعیت: {status}",
        f"🏷 نقش: {role}",
        f"💰 کیف پول: {user.wallet_balance:,} تومان",
        f"📋 اشتراک‌ها: {subscription_count}",
        f"🎟 کد دعوت: {user.referral_code.upper()}",
    ]
    return "\n".join(lines)


def build_user_inline_articles(
    users: list[User],
    *,
    subscription_counts: dict[int, int],
) -> list[InlineQueryResultArticle]:
    articles: list[InlineQueryResultArticle] = []
    for user in users:
        sub_count = subscription_counts.get(user.id, 0)
        status_emoji = "🚫" if user.is_blocked else "✅"
        title = user_display_name(user)
        if len(title) > 64:
            title = f"{title[:61]}…"
        description = f"{status_emoji} کیف پول: {user.wallet_balance:,} · اشتراک: {sub_count}"
        if len(description) > 255:
            description = f"{description[:252]}…"
        articles.append(
            InlineQueryResultArticle(
                id=f"user:{user.id}",
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(
                    message_text=inline_user_share_text(user, subscription_count=sub_count),
                ),
            )
        )
    return articles


def build_empty_inline_article(query: str) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id="empty:0",
        title="نتیجه‌ای پیدا نشد",
        description=f"برای «{query}» کاربری نیست",
        input_message_content=InputTextMessageContent(
            message_text=f"کاربری با عبارت «{query}» پیدا نشد.",
        ),
    )
