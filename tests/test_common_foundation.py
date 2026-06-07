from __future__ import annotations

from cryptography.fernet import Fernet

from vpn_bot_platform.common.crypto import SecretBox, hash_secret
from vpn_bot_platform.common.models import RateLimitBucket, SellerBot, TelegramUser


def test_secret_box_round_trip() -> None:
    key = Fernet.generate_key().decode("utf-8")
    box = SecretBox(key)

    encrypted = box.encrypt("telegram-token")

    assert encrypted != "telegram-token"
    assert box.decrypt(encrypted) == "telegram-token"


def test_secret_hash_is_stable() -> None:
    assert hash_secret("token") == hash_secret("token")
    assert hash_secret("token") != hash_secret("other-token")


def test_core_model_tables_are_named() -> None:
    assert TelegramUser.__tablename__ == "telegram_users"
    assert SellerBot.__tablename__ == "seller_bots"


def test_rate_limit_scope_fits_seller_bot_uuid() -> None:
    scope_column = RateLimitBucket.__table__.columns["scope"]

    assert scope_column.type.length >= len("seller_bot:12345678-1234-1234-1234-123456789abc")
