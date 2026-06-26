from bot.admin_inline import (
    SUBS_PREFIX,
    USERS_PREFIX,
    build_empty_inline_article,
    build_subscription_inline_articles,
    build_user_inline_articles,
    parse_inline_query,
)
from bot.db import Subscription, User


def _user(user_id: int = 1, **kwargs) -> User:
    defaults = {
        "telegram_id": 123456,
        "role": "buyer",
        "wallet_balance": 150_000,
        "referral_code": "abc123xy",
        "referred_by": None,
        "first_name": "Ali",
        "last_name": "Karimi",
        "username": "alik",
    }
    defaults.update(kwargs)
    return User(id=user_id, **defaults)


def _subscription(subscription_id: int = 1, **kwargs) -> Subscription:
    defaults = {
        "user_id": 1,
        "plan_id": None,
        "marzban_username": "sub_user_abc",
        "subscription_url": "https://panel.example/sub/abc",
        "expires_at": "2026-07-20T00:00:00+00:00",
        "traffic_gb": 20,
        "duration_days": 30,
        "discount_percent": 0,
        "base_price": 100_000,
        "duration_extra": 0,
        "final_price": 100_000,
        "purchase_source": "manual",
        "status": "active",
    }
    defaults.update(kwargs)
    return Subscription(id=subscription_id, **defaults)


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


def test_build_user_inline_articles_uses_placeholder_and_ids():
    users = [_user(1)]
    articles = build_user_inline_articles(users, subscription_counts={1: 2})

    assert articles[0].id == "user:1"
    assert articles[0].input_message_content.message_text == "—"


def test_build_subscription_inline_articles_uses_status_emoji():
    articles = build_subscription_inline_articles([_subscription()])

    assert articles[0].id == "sub:1"
    assert "sub_user_abc" in articles[0].title
    assert "20GB" in articles[0].description
    assert articles[0].input_message_content.message_text == "—"


def test_build_empty_inline_article_supports_subscription_label():
    article = build_empty_inline_article("missing", entity_label="اشتراکی")

    assert "اشتراکی" in article.description


def test_inline_prefix_constants():
    assert USERS_PREFIX == "users:"
    assert SUBS_PREFIX == "subs:"
