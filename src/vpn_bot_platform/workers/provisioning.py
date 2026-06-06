from __future__ import annotations

import asyncio
import logging

from vpn_bot_platform.common.config import get_settings
from vpn_bot_platform.common.db import init_engine


async def run() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logging.getLogger(__name__).info("Provisioning worker started")
    init_engine(settings.database_url)
    while True:
        await asyncio.sleep(60)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
