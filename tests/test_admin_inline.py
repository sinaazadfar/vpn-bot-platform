from bot.admin_inline import build_empty_inline_article, build_user_inline_articles, inline_user_share_text
from bot.db import User


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


def test_inline_user_share_text_includes_status_and_wallet():
    text = inline_user_share_text(_user(), subscription_count=2)

    assert "Ali Karimi" in text
    assert "123456" in text
    assert "✅ فعال" in text
    assert "150,000" in text
    assert "اشتراک‌ها: 2" in text


def test_build_user_inline_articles_uses_emoji_and_counts():
    users = [_user(1), _user(2, is_blocked=True, first_name="Blocked", last_name=None, username=None, telegram_id=999)]
    articles = build_user_inline_articles(users, subscription_counts={1: 3, 2: 0})

    assert len(articles) == 2
    assert articles[0].id == "user:1"
    assert "اشتراک: 3" in articles[0].description
    assert "🚫" in articles[1].description
    assert articles[1].input_message_content.message_text is not None
    assert "Blocked" in articles[1].input_message_content.message_text


def test_build_empty_inline_article_mentions_query():
    article = build_empty_inline_article("sub_abc")

    assert "sub_abc" in article.title or "sub_abc" in article.description
    assert article.input_message_content.message_text is not None
    assert "sub_abc" in article.input_message_content.message_text
