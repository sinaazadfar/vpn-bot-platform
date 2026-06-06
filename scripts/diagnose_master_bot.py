from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from vpn_bot_platform.common.config import get_settings


async def main() -> None:
    settings = get_settings()
    session = AiohttpSession(timeout=10)
    bot = Bot(settings.master_bot_token, session=session)
    try:
        me = await bot.get_me()
        webhook = await bot.get_webhook_info()
        print(f"bot_username={me.username}")
        print(f"bot_id={me.id}")
        print(f"super_user_telegram_id={settings.super_user_telegram_id}")
        print(f"webhook_url_set={bool(webhook.url)}")
        print(f"pending_update_count={webhook.pending_update_count}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
