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
from vpn_bot_platform.master_bot.filters import SuperUserFilter
from vpn_bot_platform.master_bot.handlers.basic import router as basic_router
from vpn_bot_platform.master_bot.services.resellers import ResellerService


async def run() -> None:
    settings = get_settings()
    if not settings.master_bot_token:
        raise RuntimeError("MASTER_BOT_TOKEN is required")
    if settings.super_user_telegram_id is None:
        raise RuntimeError("SUPER_USER_TELEGRAM_ID is required")

    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger(__name__)

    init_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        await create_all()

    reseller_service = ResellerService(SecretBox(settings.fernet_key), settings)

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(
        RateLimitMiddleware(
            RateLimitConfig(scope="master_bot", limit=settings.bot_rate_limit_per_minute)
        )
    )
    basic_router.message.filter(SuperUserFilter(settings))
    dp.include_router(basic_router)

    while True:
        bot = Bot(settings.master_bot_token)
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("Master bot polling started")
            await dp.start_polling(bot, reseller_service=reseller_service)
            break
        except TelegramNetworkError as exc:
            logger.warning("Telegram network error in master bot polling: %s", exc)
            await asyncio.sleep(5)
        finally:
            await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
