from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from bot.context import AppContext
from bot.db import Repository
from bot.forced_join import (
    evaluate_forced_join,
    forced_join_keyboard,
    forced_join_recheck_failed_alert,
    forced_join_text,
)
from bot.formatting import with_footer
from bot.menu_helpers import main_menu_for_user
from bot.middleware.block_check import _is_admin_event, _telegram_user_id

_JOIN_SUCCESS_TOAST = "عضویت تأیید شد ✅"
_WELCOME_TEXT = "به ربات فروش VPN خوش آمدید."


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

        is_recheck = getattr(event, "data", None) == "join:recheck"

        async with ctx.database.session() as db:
            repository = Repository(db)
            chats = await repository.list_required_chats()
            if not chats:
                return await handler(event, data)
            allowed, block_reason = await evaluate_forced_join(event.bot, user_id, chats)

        if allowed:
            if is_recheck:
                await self._complete_join_recheck(event, ctx)
                return None
            return await handler(event, data)

        text = with_footer(forced_join_text(chats))
        keyboard = forced_join_keyboard(chats)
        if isinstance(event, CallbackQuery):
            if is_recheck:
                await event.answer(forced_join_recheck_failed_alert(block_reason), show_alert=True)
            else:
                await event.answer()
            await _safe_edit_text(event.message, text, keyboard)
            return None
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard)
            return None
        return None

    async def _complete_join_recheck(self, event: TelegramObject, ctx: AppContext) -> None:
        from_user = getattr(event, "from_user", None)
        if from_user is None:
            answer = getattr(event, "answer", None)
            if callable(answer):
                await answer()
            return

        answer = getattr(event, "answer", None)
        if callable(answer):
            await answer(_JOIN_SUCCESS_TOAST)
        async with ctx.database.session() as db:
            repository = Repository(db)
            user = await repository.ensure_user_from_telegram(from_user, ctx.settings.admin_ids)
            keyboard = await main_menu_for_user(repository, user, ctx)
        text = with_footer(_WELCOME_TEXT)
        message = getattr(event, "message", None)
        edited = await _safe_edit_text(message, text, keyboard)
        if not edited:
            bot = getattr(event, "bot", None)
            if bot is not None:
                await bot.send_message(from_user.id, text, reply_markup=keyboard)


def register_user_middlewares(dp: Dispatcher) -> None:
    from bot.middleware.block_check import BlockCheckMiddleware

    for observer_name in ("message", "callback_query"):
        observer = getattr(dp, observer_name)
        observer.middleware(BlockCheckMiddleware())
        observer.middleware(ForcedJoinMiddleware())
