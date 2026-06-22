from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from bot.db import Repository


class VolumeQuotaError(RuntimeError):
    pass


@dataclass(frozen=True)
class VolumeQuota:
    limit_gb: int
    used_gb: int
    requested_gb: int

    @property
    def remaining_gb(self) -> int:
        return max(0, self.limit_gb - self.used_gb)


class MasterVolumeQuota:
    def __init__(self, *, platform_database_url: str, seller_bot_id: str) -> None:
        self.platform_database_url = platform_database_url
        self.seller_bot_id = seller_bot_id

    @property
    def enabled(self) -> bool:
        return bool(self.platform_database_url and self.seller_bot_id)

    async def ensure_available(self, repository: Repository, *, requested_gb: int) -> VolumeQuota | None:
        if not self.enabled or requested_gb <= 0:
            return None
        limit_gb = await self._volume_limit_gb()
        used_gb = await repository.active_subscription_traffic_gb()
        quota = VolumeQuota(limit_gb=limit_gb, used_gb=used_gb, requested_gb=requested_gb)
        if quota.remaining_gb < requested_gb:
            raise VolumeQuotaError("seller_bot_volume_limit_exceeded")
        return quota

    async def status(self, repository: Repository) -> VolumeQuota | None:
        if not self.enabled:
            return None
        limit_gb = await self._volume_limit_gb()
        used_gb = await repository.active_subscription_traffic_gb()
        return VolumeQuota(limit_gb=limit_gb, used_gb=used_gb, requested_gb=0)

    async def _volume_limit_gb(self) -> int:
        engine = create_async_engine(self.platform_database_url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT volume_limit_gb FROM seller_bots WHERE id = :seller_bot_id"),
                    {"seller_bot_id": self.seller_bot_id},
                )
                value = result.scalar_one_or_none()
        finally:
            await engine.dispose()
        return int(value or 0)
