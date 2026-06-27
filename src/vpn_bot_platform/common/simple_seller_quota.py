from __future__ import annotations

from pathlib import Path

import aiosqlite

CONTAINER_SELLER_DATA_ROOT = Path("/app/data/sellers")


def simple_seller_database_paths(
    seller_bot_id: str,
    *,
    seller_data_host_path: str | None = None,
) -> list[Path]:
    paths = [CONTAINER_SELLER_DATA_ROOT / seller_bot_id / "bot.sqlite3"]
    if seller_data_host_path:
        host_path = Path(seller_data_host_path) / seller_bot_id / "bot.sqlite3"
        if host_path not in paths:
            paths.append(host_path)
    return paths


async def read_simple_seller_used_gb(
    *,
    seller_bot_id: str,
    seller_data_host_path: str | None = None,
) -> int:
    for database_path in simple_seller_database_paths(
        seller_bot_id,
        seller_data_host_path=seller_data_host_path,
    ):
        if not database_path.is_file():
            continue
        async with aiosqlite.connect(database_path) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(traffic_gb), 0) AS total "
                "FROM subscriptions WHERE status = 'active'"
            ) as cursor:
                row = await cursor.fetchone()
                return int(row[0] or 0)
    return 0
