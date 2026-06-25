from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.context import AppContext
from bot.db import Repository
from bot.forced_join import (
    evaluate_forced_join,
    forced_join_keyboard,
    forced_join_recheck_failed_alert,
    forced_join_success_text,
    forced_join_text,
)
from bot.formatting import with_footer
from bot.menu_helpers import main_menu_for_user
from bot.middleware.block_check import _is_admin_event, _telegram_user_id


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

        is_recheck = isinstance(event, CallbackQuery) and event.data == "join:recheck"

        async with ctx.database.session() as db:
            repository = Repository(db)
            chats = await repository.list_required_chats()
            if not chats:
                return await handler(event, data)
            allowed, block_reason = await evaluate_forced_join(event.bot, user_id, chats)

        if allowed:
            if is_recheck:
                await self._show_main_menu(event, ctx)
                return None
            return await handler(event, data)

        text = with_footer(forced_join_text(chats))
        keyboard = forced_join_keyboard(chats)
        if isinstance(event, CallbackQuery):
            if is_recheck:
                await event.answer(forced_join_recheck_failed_alert(block_reason), show_alert=True)
            else:
                await event.answer()
            await event.message.edit_text(text, reply_markup=keyboard)
            return None
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard)
            return None
        return None

    async def _show_main_menu(self, event: CallbackQuery | Message, ctx: AppContext) -> None:
        from_user = event.from_user
        if from_user is None:
            return
        async with ctx.database.session() as db:
            repository = Repository(db)
            user = await repository.ensure_user_from_telegram(from_user, ctx.settings.admin_ids)
            keyboard = await main_menu_for_user(repository, user, ctx)
        text = with_footer(forced_join_success_text())
        if isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.edit_text(text, reply_markup=keyboard)
        else:
            await event.answer(text, reply_markup=keyboard)


def register_user_middlewares(dp: Dispatcher) -> None:
    from bot.middleware.block_check import BlockCheckMiddleware

    for observer_name in ("message", "callback_query"):
        observer = getattr(dp, observer_name)
        observer.middleware(BlockCheckMiddleware())
        observer.middleware(ForcedJoinMiddleware())
