from __future__ import annotations

from types import SimpleNamespace

from vpn_bot_platform.seller_bot.inline_search import (
    SUBS_PREFIX,
    USERS_PREFIX,
    build_customer_inline_articles,
    build_empty_inline_article,
    build_service_inline_articles,
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


def test_build_customer_inline_articles_uses_placeholder_and_ids():
    customers = [_customer()]
    articles = build_customer_inline_articles(customers)

    assert articles[0].id == "user:buyer-uuid-1"
    assert articles[0].input_message_content.message_text == "—"


def test_build_service_inline_articles_uses_status_emoji():
    articles = build_service_inline_articles([_service()])

    assert articles[0].id == "service:service-uuid-1"
    assert "sub_user_abc" in articles[0].title
    assert "20GB" in articles[0].description
    assert articles[0].input_message_content.message_text == "—"


def test_build_empty_inline_article_supports_service_label():
    article = build_empty_inline_article("missing", entity_label="سرویسی")

    assert "سرویسی" in article.description


def test_inline_prefix_constants():
    assert USERS_PREFIX == "users:"
    assert SUBS_PREFIX == "subs:"
