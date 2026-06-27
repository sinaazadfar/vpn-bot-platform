from __future__ import annotations

from types import SimpleNamespace

from aiogram.types import InlineKeyboardMarkup

from vpn_bot_platform.seller_bot.inline_search import (
    SUBS_PREFIX,
    USERS_PREFIX,
    build_customer_inline_article,
    build_empty_inline_article,
    build_service_inline_article,
    parse_inline_query,
)


def _telegram_user(**kwargs):
    defaults = {
        "id": 123456,
        "username": "buyer",
        "first_name": "Ali",
        "last_name": "Test",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _buyer(**kwargs):
    defaults = {
        "id": "buyer-uuid-1",
        "wallet_balance": 150_000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _customer(**kwargs):
    return SimpleNamespace(
        buyer=_buyer(**kwargs.pop("buyer", {})),
        telegram_user=_telegram_user(**kwargs.pop("telegram_user", {})),
        **kwargs,
    )


def _service(**kwargs):
    defaults = {
        "id": "service-uuid-1",
        "marzban_username": "sub_user_abc",
        "data_limit_gb": 20,
        "is_active": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _empty_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[])


def test_parse_inline_query_users_prefix():
    mode, query = parse_inline_query("users: ali test")

    assert mode == "users"
    assert query == "ali test"


def test_parse_inline_query_subs_prefix():
    mode, query = parse_inline_query("subs:my_sub")

    assert mode == "subs"
    assert query == "my_sub"


def test_parse_inline_query_without_prefix_returns_none_mode():
    mode, query = parse_inline_query("plain text")

    assert mode is None
    assert query == "plain text"


def test_build_customer_inline_article_includes_full_message_and_markup():
    customer = _customer()
    message_text = "اطلاعات کاربر\nآیدی تلگرام: 123456\n\n\n➖➖➖"
    markup = _empty_markup()
    article = build_customer_inline_article(customer, message_text=message_text, reply_markup=markup)

    assert article.id == "user:buyer-uuid-1"
    assert article.input_message_content.message_text == message_text
    assert article.reply_markup == markup


def test_build_service_inline_article_includes_full_message_and_markup():
    service = _service()
    message_text = "جزئیات سرویس\nنام کاربری: sub_user_abc\n\n\n➖➖➖"
    markup = _empty_markup()
    article = build_service_inline_article(service, message_text=message_text, reply_markup=markup)

    assert article.id == "service:service-uuid-1"
    assert "sub_user_abc" in article.title
    assert "20GB" in article.description
    assert article.input_message_content.message_text == message_text
    assert article.reply_markup == markup


def test_build_empty_inline_article_supports_service_label():
    article = build_empty_inline_article("missing", entity_label="سرویسی")

    assert "سرویسی" in article.description


def test_inline_prefix_constants():
    assert USERS_PREFIX == "users:"
    assert SUBS_PREFIX == "subs:"
