from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.context import AppContext
from bot.db import Database
from bot.formatting import MESSAGE_FOOTER
from bot.handlers import setup_routers
from bot.marzban import MarzbanClient

def add_message_footer(bot: Bot) -> None:
    original_send_message = bot.send_message
    original_send_photo = bot.send_photo

    def with_footer(value: str | None) -> str | None:
        if not value or value.endswith(MESSAGE_FOOTER):
            return value
        return f"{value}{MESSAGE_FOOTER}"

    async def send_message_with_footer(chat_id, text, *args, **kwargs):
        return await original_send_message(chat_id, with_footer(text), *args, **kwargs)

    async def send_photo_with_footer(chat_id, photo, *args, **kwargs):
        kwargs["caption"] = with_footer(kwargs.get("caption"))
        return await original_send_photo(chat_id, photo, *args, **kwargs)

    bot.send_message = send_message_with_footer
    bot.send_photo = send_photo_with_footer


async def main() -> None:
    settings = get_settings()
    database = Database(settings.database_path)
    await database.init()

    bot = Bot(settings.bot_token)
    add_message_footer(bot)
    dp = Dispatcher(storage=MemoryStorage())
    dp["ctx"] = AppContext(
        settings=settings,
        database=database,
        marzban=MarzbanClient(
            settings.marzban_base_url,
            settings.marzban_username,
            settings.marzban_password,
            settings.marzban_token,
            settings.marzban_default_proxies_json,
        ),
    )
    dp.include_router(setup_routers())
    await dp.start_polling(bot)
