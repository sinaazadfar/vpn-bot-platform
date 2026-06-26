from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand

from bot.db import Repository

_START_COMMAND = BotCommand(command="start", description="شروع و منوی اصلی")
_TRIAL_COMMAND = BotCommand(command="trial", description="دریافت تست رایگان")


async def sync_bot_commands(bot: Bot, repository: Repository) -> None:
    commands = [_START_COMMAND]
    if await repository.get_trial_enabled():
        commands.append(_TRIAL_COMMAND)
    await bot.set_my_commands(commands)
