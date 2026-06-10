from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from vpn_bot_platform.common.config import Settings


class SuperUserFilter(BaseFilter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if event.from_user is None:
            return False
        return event.from_user.id == self.settings.super_user_telegram_id
