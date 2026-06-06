from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage

from vpn_bot_platform.common.config import get_settings
from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import create_all, init_engine
from vpn_bot_platform.common.rate_limit import RateLimitConfig, RateLimitMiddleware
from vpn_bot_platform.seller_bot.handlers import router as seller_router
from vpn_bot_platform.seller_bot.provisioning import ProvisioningService
from vpn_bot_platform.seller_bot.services import SellerContextService


async def run() -> None:
    settings = get_settings()
    if not settings.seller_bot_id:
        raise RuntimeError("SELLER_BOT_ID is required")
    if not settings.seller_bot_token:
        raise RuntimeError("SELLER_BOT_TOKEN is required")

    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger(__name__)

    init_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        await create_all()

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(
        RateLimitMiddleware(
            RateLimitConfig(
                scope=f"seller_bot:{settings.seller_bot_id}",
                limit=settings.bot_rate_limit_per_minute,
            )
        )
    )
    dp.include_router(seller_router)
    seller_context = SellerContextService(settings.seller_bot_id, settings)
    provisioning_service = ProvisioningService(
        seller_bot_id=settings.seller_bot_id,
        settings=settings,
        secret_box=SecretBox(settings.fernet_key),
    )

    while True:
        bot = Bot(settings.seller_bot_token)
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("Seller bot polling started for seller_bot_id=%s", settings.seller_bot_id)
            await dp.start_polling(
                bot,
                seller_context=seller_context,
                provisioning_service=provisioning_service,
            )
            break
        except TelegramNetworkError as exc:
            logger.warning("Telegram network error in seller bot polling: %s", exc)
            await asyncio.sleep(5)
        finally:
            await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
