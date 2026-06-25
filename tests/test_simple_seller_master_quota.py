from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from vpn_bot_platform.common.config import get_settings
from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine, session_scope
from vpn_bot_platform.common.models import SellerBotUiProfile
from vpn_bot_platform.common.repositories import get_seller_bot_quota_usage
from vpn_bot_platform.common.simple_seller_quota import read_simple_seller_used_gb
from vpn_bot_platform.master_bot.services.resellers import ResellerService


def _create_simple_seller_sqlite(path: Path, *, active_traffic_gb: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER,
            marzban_username TEXT NOT NULL,
            subscription_url TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            traffic_gb INTEGER NOT NULL,
            duration_days INTEGER NOT NULL DEFAULT 30,
            discount_percent INTEGER NOT NULL DEFAULT 0,
            base_price INTEGER NOT NULL DEFAULT 0,
            duration_extra INTEGER NOT NULL DEFAULT 0,
            final_price INTEGER NOT NULL DEFAULT 0,
            purchase_source TEXT NOT NULL DEFAULT 'legacy',
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO subscriptions (
            user_id, marzban_username, subscription_url, expires_at, traffic_gb,
            status, created_at, updated_at
        ) VALUES (1, 'user1', 'https://panel.example/sub/user1', '2099-01-01T00:00:00+00:00', ?, 'active', 'now', 'now')
        """,
        (active_traffic_gb,),
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_read_simple_seller_used_gb_from_sqlite(tmp_path) -> None:
    database_path = tmp_path / "seller-1" / "bot.sqlite3"
    _create_simple_seller_sqlite(database_path, active_traffic_gb=18)

    used_gb = await read_simple_seller_used_gb(
        seller_bot_id="seller-1",
        seller_data_host_path=str(tmp_path),
    )

    assert used_gb == 18


@pytest.mark.asyncio
async def test_master_quota_reads_simple_seller_sqlite_usage(tmp_path, monkeypatch) -> None:
    seller_data_root = tmp_path / "sellers"

    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode("utf-8"))
    monkeypatch.setenv("SELLER_DATA_HOST_PATH", str(seller_data_root))
    get_settings.cache_clear()

    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(get_settings().fernet_key))

    try:
        await service.register_reseller(telegram_id=111, display_name="Seller A")
        seller_bot = await service.register_seller_bot(
            reseller_telegram_id=111,
            bot_name="simple seller",
            bot_token="123:secret",
            volume_limit_gb=100,
            ui_profile=SellerBotUiProfile.SIMPLE_SELLER,
        )
        _create_simple_seller_sqlite(
            seller_data_root / seller_bot.id / "bot.sqlite3",
            active_traffic_gb=25,
        )

        async with session_scope() as session:
            usage = await get_seller_bot_quota_usage(session, seller_bot_id=seller_bot.id)

        quota = await service.seller_bot_quota(seller_bot_id=seller_bot.id)
    finally:
        await dispose_engine()
        get_settings.cache_clear()

    assert usage.used_gb == 25
    assert usage.limit_gb == 100
    assert usage.remaining_gb == 75
    assert quota.used_gb == 25
