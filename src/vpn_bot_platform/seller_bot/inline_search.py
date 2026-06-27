from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent

from vpn_bot_platform.common.models import VpnService
from vpn_bot_platform.seller_bot.services import SellerCustomer

INLINE_RESULTS_LIMIT = 20
USERS_PREFIX = "users:"
SUBS_PREFIX = "subs:"
MAX_INLINE_MESSAGE_LENGTH = 4096


def parse_inline_query(raw: str | None) -> tuple[str | None, str]:
    text = (raw or "").strip()
    if text.startswith(USERS_PREFIX):
        return "users", text[len(USERS_PREFIX) :].strip()
    if text.startswith(SUBS_PREFIX):
        return "subs", text[len(SUBS_PREFIX) :].strip()
    return None, text


def _service_status_emoji(*, is_active: bool) -> str:
    return "✅" if is_active else "⏸"


def customer_display_name(user) -> str:
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    if user.username:
        return f"@{user.username}" if not full_name else f"{full_name} (@{user.username})"
    return full_name or str(user.id)


def _clip_inline_message(text: str) -> str:
    if len(text) <= MAX_INLINE_MESSAGE_LENGTH:
        return text
    return f"{text[: MAX_INLINE_MESSAGE_LENGTH - 1]}…"


def build_service_inline_article(
    service: VpnService,
    *,
    message_text: str,
    reply_markup: InlineKeyboardMarkup,
) -> InlineQueryResultArticle:
    emoji = _service_status_emoji(is_active=service.is_active)
    title = service.marzban_username
    if len(title) > 64:
        title = f"{title[:61]}…"
    traffic = "نامحدود" if service.data_limit_gb is None else f"{service.data_limit_gb}GB"
    description = f"{emoji} {traffic} · {service.marzban_username}"
    if len(description) > 255:
        description = f"{description[:252]}…"
    return InlineQueryResultArticle(
        id=f"service:{service.id}",
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(message_text=_clip_inline_message(message_text)),
        reply_markup=reply_markup,
    )


def build_customer_inline_article(
    customer: SellerCustomer,
    *,
    message_text: str,
    reply_markup: InlineKeyboardMarkup,
) -> InlineQueryResultArticle:
    buyer_id = customer.buyer.id
    title = customer_display_name(customer.telegram_user)
    if len(title) > 64:
        title = f"{title[:61]}…"
    wallet = f"{float(customer.buyer.wallet_balance):,.0f}"
    description = f"💰 {wallet} تومان · 🆔 {customer.telegram_user.id}"
    if len(description) > 255:
        description = f"{description[:252]}…"
    return InlineQueryResultArticle(
        id=f"user:{buyer_id}",
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(message_text=_clip_inline_message(message_text)),
        reply_markup=reply_markup,
    )


def build_empty_inline_article(query: str, *, entity_label: str = "کاربری") -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id="empty:0",
        title="نتیجه‌ای پیدا نشد",
        description=f"برای «{query}» {entity_label} نیست",
        input_message_content=InputTextMessageContent(
            message_text=f"{entity_label.capitalize()} با عبارت «{query}» پیدا نشد.",
        ),
    )
