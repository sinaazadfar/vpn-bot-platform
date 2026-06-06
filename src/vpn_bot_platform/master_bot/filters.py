from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from vpn_bot_platform.common.config import Settings


class SuperUserFilter(BaseFilter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False
        return message.from_user.id == self.settings.super_user_telegram_id

