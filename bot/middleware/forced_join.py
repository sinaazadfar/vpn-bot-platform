from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.context import AppContext
from bot.db import Repository
from bot.forced_join import check_forced_join, forced_join_keyboard, forced_join_text
from bot.formatting import with_footer
from bot.middleware.block_check import _is_admin_event, _is_start_message, _telegram_user_id


class ForcedJoinMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        ctx: AppContext | None = data.get("ctx")
        if ctx is None:
            return await handler(event, data)

        user_id = _telegram_user_id(event)
        if user_id is None or _is_admin_event(event, ctx.settings.admin_ids):
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "join:recheck":
            pass
        elif _is_start_message(event):
            return await handler(event, data)

        async with ctx.database.session() as db:
            repository = Repository(db)
            chats = await repository.list_required_chats()
            if not chats:
                return await handler(event, data)
            allowed = await check_forced_join(event.bot, user_id, chats)

        if allowed:
            return await handler(event, data)

        text = with_footer(forced_join_text(chats))
        keyboard = forced_join_keyboard(chats)
        if isinstance(event, CallbackQuery):
            if event.data == "join:recheck":
                await event.answer("هنوز عضو همه کانال‌ها نشده‌اید.", show_alert=True)
            await event.message.edit_text(text, reply_markup=keyboard)
            return None
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard)
            return None
        return None
