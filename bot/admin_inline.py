from __future__ import annotations

from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from bot.admin_users import subscription_status_emoji, user_display_name
from bot.db import Subscription, User

INLINE_RESULTS_LIMIT = 20
USERS_PREFIX = "users:"
SUBS_PREFIX = "subs:"
INLINE_PLACEHOLDER_TEXT = "—"


def parse_inline_query(raw: str | None) -> tuple[str | None, str]:
    text = (raw or "").strip()
    if text.startswith(USERS_PREFIX):
        return "users", text[len(USERS_PREFIX) :].strip()
    if text.startswith(SUBS_PREFIX):
        return "subs", text[len(SUBS_PREFIX) :].strip()
    return None, text


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
                input_message_content=InputTextMessageContent(message_text=INLINE_PLACEHOLDER_TEXT),
            )
        )
    return articles


def build_subscription_inline_articles(subscriptions: list[Subscription]) -> list[InlineQueryResultArticle]:
    articles: list[InlineQueryResultArticle] = []
    for subscription in subscriptions:
        emoji = subscription_status_emoji(subscription.status)
        title = subscription.marzban_username
        if len(title) > 64:
            title = f"{title[:61]}…"
        description = f"{emoji} {subscription.traffic_gb}GB · {subscription.duration_days} روز"
        if len(description) > 255:
            description = f"{description[:252]}…"
        articles.append(
            InlineQueryResultArticle(
                id=f"sub:{subscription.id}",
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(message_text=INLINE_PLACEHOLDER_TEXT),
            )
        )
    return articles


def build_empty_inline_article(query: str, *, entity_label: str = "کاربری") -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id="empty:0",
        title="نتیجه‌ای پیدا نشد",
        description=f"برای «{query}» {entity_label} نیست",
        input_message_content=InputTextMessageContent(
            message_text=f"{entity_label.capitalize()} با عبارت «{query}» پیدا نشد.",
        ),
    )
