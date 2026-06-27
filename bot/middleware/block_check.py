from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot import constants as c
from bot.context import AppContext
from bot.db import Repository
from bot.formatting import with_footer
from bot.keyboards import back_to_main_keyboard

_BLOCKED_TEXT = "حساب شما توسط ادمین مسدود شده است."

_ADMIN_REPLY_LABELS = {
    c.ADMIN_PANEL,
    c.ADMIN_PLANS,
    c.ADMIN_QUOTA,
    c.ADMIN_USERS,
    c.ADMIN_PAYMENTS,
    c.ADMIN_BROADCAST,
}


def _telegram_user_id(event: TelegramObject) -> int | None:
    from_user = getattr(event, "from_user", None)
    return from_user.id if from_user else None


def _is_start_message(event: TelegramObject) -> bool:
    return isinstance(event, Message) and (event.text or "").startswith("/start")


def _is_admin_event(event: TelegramObject, admin_ids: set[int]) -> bool:
    user_id = _telegram_user_id(event)
    if user_id is not None and user_id in admin_ids:
        return True
    if isinstance(event, CallbackQuery):
        data = event.data or ""
        if data.startswith(("admin:", "adm:", "pay_ok:", "pay_no:")):
            return True
    if isinstance(event, Message):
        text = (event.text or "").strip()
        if text.startswith("/adjust") or text in _ADMIN_REPLY_LABELS:
            return True
    return False


class BlockCheckMiddleware(BaseMiddleware):
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

        if _is_start_message(event):
            return await handler(event, data)

        async with ctx.database.session() as db:
            user = await Repository(db).get_user_by_telegram_id(user_id)
        if user is None or not user.is_blocked:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer(_BLOCKED_TEXT, show_alert=True)
            return None

        if isinstance(event, Message):
            await event.answer(with_footer(_BLOCKED_TEXT), reply_markup=back_to_main_keyboard())
            return None

        return None
