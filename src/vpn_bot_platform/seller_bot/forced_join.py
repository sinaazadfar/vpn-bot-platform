from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from vpn_bot_platform.common.db import session_scope
from vpn_bot_platform.common.forced_join import FORCED_JOIN_CHATS_KEY, ForcedJoinChat, decode_forced_join_chats
from vpn_bot_platform.common.repositories import get_global_setting


async def get_required_join_chats() -> list[ForcedJoinChat]:
    async with session_scope() as session:
        setting = await get_global_setting(session, key=FORCED_JOIN_CHATS_KEY)
        return decode_forced_join_chats(setting.value if setting else None)


async def missing_required_chats(bot: Bot, *, user_id: int) -> list[ForcedJoinChat]:
    missing: list[ForcedJoinChat] = []
    for chat in await get_required_join_chats():
        try:
            member = await bot.get_chat_member(chat.chat_id, user_id)
        except TelegramAPIError:
            missing.append(chat)
            continue
        if member.status in {"left", "kicked"}:
            missing.append(chat)
    return missing
