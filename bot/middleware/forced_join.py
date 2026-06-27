from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from bot.context import AppContext
from bot.db import Repository
from bot.forced_join import evaluate_forced_join, forced_join_keyboard, forced_join_text
from bot.formatting import with_footer
from bot.middleware.block_check import _is_admin_event, _telegram_user_id


async def _safe_edit_text(message: Message | None, text: str, reply_markup: InlineKeyboardMarkup) -> bool:
    if message is None:
        return False
    try:
        await message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return True
        return False


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

        async with ctx.database.session() as db:
            repository = Repository(db)
            chats = await repository.list_required_chats()
            if not chats:
                return await handler(event, data)
            allowed, _block_reason = await evaluate_forced_join(event.bot, user_id, chats)

        if allowed:
            return await handler(event, data)

        bot_username = (await event.bot.me()).username
        if not bot_username:
            return await handler(event, data)

        text = with_footer(forced_join_text(chats))
        keyboard = forced_join_keyboard(chats, bot_username)
        if isinstance(event, CallbackQuery):
            await event.answer()
            await _safe_edit_text(event.message, text, keyboard)
            return None
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard)
            return None
        return None


def register_user_middlewares(dp: Dispatcher) -> None:
    from bot.middleware.block_check import BlockCheckMiddleware

    for observer_name in ("message", "callback_query"):
        observer = getattr(dp, observer_name)
        observer.middleware(BlockCheckMiddleware())
        observer.middleware(ForcedJoinMiddleware())
