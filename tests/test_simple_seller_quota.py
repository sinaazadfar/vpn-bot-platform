from __future__ import annotations

import sqlite3

import pytest
import pytest_asyncio

from bot.db import Database, Repository
from bot.quota import MasterVolumeQuota, VolumeQuotaError


@pytest_asyncio.fixture
async def repository(tmp_path):
    database = Database(tmp_path / "seller.sqlite3")
    await database.init()
    async with database.session() as db:
        yield Repository(db)


def _platform_database_url(tmp_path, *, seller_bot_id: str, volume_limit_gb: int) -> str:
    path = tmp_path / "platform.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE seller_bots (id TEXT PRIMARY KEY, volume_limit_gb INTEGER)")
    conn.execute(
        "INSERT INTO seller_bots (id, volume_limit_gb) VALUES (?, ?)",
        (seller_bot_id, volume_limit_gb),
    )
    conn.commit()
    conn.close()
    return f"sqlite+aiosqlite:///{path.as_posix()}"


@pytest.mark.asyncio
async def test_simple_seller_quota_allows_purchase_within_master_limit(tmp_path, repository):
    quota = MasterVolumeQuota(
        platform_database_url=_platform_database_url(tmp_path, seller_bot_id="seller-1", volume_limit_gb=20),
        seller_bot_id="seller-1",
    )

    result = await quota.ensure_available(repository, requested_gb=10)

    assert result is not None
    assert result.limit_gb == 20
    assert result.used_gb == 0
    assert result.remaining_gb == 20


@pytest.mark.asyncio
async def test_simple_seller_quota_status_shows_used_and_remaining(tmp_path, repository):
    user = await repository.ensure_user(1002, set())
    await repository.adjust_wallet(user.id, 1_000_000, "seed")
    await repository.db.commit()
    user = await repository.get_user_by_telegram_id(1002)
    settings = await repository.update_pricing_settings(per_gb_price=1_000)
    offer = repository.build_offer(settings, 12, 30, "manual")
    await repository.create_subscription_after_charge(
        user,
        offer,
        "existing_user",
        "https://panel.example/sub/existing_user",
        "2026-07-20T00:00:00+00:00",
    )
    quota = MasterVolumeQuota(
        platform_database_url=_platform_database_url(tmp_path, seller_bot_id="seller-1", volume_limit_gb=20),
        seller_bot_id="seller-1",
    )

    status = await quota.status(repository)

    assert status is not None
    assert status.limit_gb == 20
    assert status.used_gb == 12
    assert status.remaining_gb == 8


@pytest.mark.asyncio
async def test_simple_seller_quota_blocks_purchase_over_master_limit(tmp_path, repository):
    user = await repository.ensure_user(1001, set())
    await repository.adjust_wallet(user.id, 1_000_000, "seed")
    await repository.db.commit()
    user = await repository.get_user_by_telegram_id(1001)
    settings = await repository.update_pricing_settings(per_gb_price=1_000)
    offer = repository.build_offer(settings, 15, 30, "manual")
    await repository.create_subscription_after_charge(
        user,
        offer,
        "existing_user",
        "https://panel.example/sub/existing_user",
        "2026-07-20T00:00:00+00:00",
    )
    quota = MasterVolumeQuota(
        platform_database_url=_platform_database_url(tmp_path, seller_bot_id="seller-1", volume_limit_gb=20),
        seller_bot_id="seller-1",
    )

    with pytest.raises(VolumeQuotaError, match="seller_bot_volume_limit_exceeded"):
        await quota.ensure_available(repository, requested_gb=10)
