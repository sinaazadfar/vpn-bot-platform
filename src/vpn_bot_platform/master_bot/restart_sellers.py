from __future__ import annotations

import asyncio
import logging

from vpn_bot_platform.common.config import get_settings
from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import init_engine, session_scope
from vpn_bot_platform.common.models import SellerBotStatus
from vpn_bot_platform.common.repositories import list_seller_bots_by_status
from vpn_bot_platform.master_bot.services.resellers import ResellerService


async def run() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    init_engine(settings.database_url)
    service = ResellerService(SecretBox(settings.fernet_key), settings)
    async with session_scope() as session:
        seller_bots = await list_seller_bots_by_status(
            session,
            statuses=[SellerBotStatus.RUNNING.value],
        )
    for seller_bot in seller_bots:
        await service.start_seller_bot(seller_bot_id=seller_bot.id)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

