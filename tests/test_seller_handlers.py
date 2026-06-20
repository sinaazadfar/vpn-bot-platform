from vpn_bot_platform.seller_bot.handlers import support_contact_url


def test_support_contact_url_for_username() -> None:
    assert support_contact_url("@support_user") == "https://t.me/support_user"
    assert support_contact_url("support_user") == "https://t.me/support_user"


def test_support_contact_url_for_telegram_id() -> None:
    assert support_contact_url(444) == "tg://user?id=444"


def test_support_contact_url_empty() -> None:
    assert support_contact_url(None) is None
    assert support_contact_url("") is None
