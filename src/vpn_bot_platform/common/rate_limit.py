from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from vpn_bot_platform.common.db import session_scope
from vpn_bot_platform.common.repositories import consume_rate_limit_token

ADMIN_THROTTLED_MESSAGE = "درخواست‌های ادمین زیاد شد. لطفا کمی صبر کنید."
SENSITIVE_ADMIN_BUCKET_KEYS = frozenset(
    {
        "approvepay",
        "rejectpay",
        "provision",
        "approvetx",
        "rejecttx",
        "closeticket",
        "renew",
    }
)


@dataclass(frozen=True)
class RateLimitConfig:
    scope: str
    limit: int = 20
    window_seconds: int = 60


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)
        command = _command_name(event)
        bucket_key = command or "message"
        async with session_scope() as session:
            allowed, _remaining = await consume_rate_limit_token(
                session,
                scope=self.config.scope,
                identity=str(event.from_user.id),
                bucket_key=bucket_key,
                limit=self.config.limit,
                window_seconds=self.config.window_seconds,
            )
        if not allowed:
            await event.answer("Too many requests. Please wait a minute and try again.")
            return None
        return await handler(event, data)


@dataclass(frozen=True)
class AdminRateLimitConfig:
    scope: str
    limit: int = 10
    sensitive_limit: int = 5
    window_seconds: int = 60
    sensitive_bucket_keys: frozenset[str] = SENSITIVE_ADMIN_BUCKET_KEYS


class AdminRateLimitMiddleware(BaseMiddleware):
    def __init__(
        self,
        config: AdminRateLimitConfig,
        is_admin: Callable[[int], Awaitable[bool]],
    ) -> None:
        self.config = config
        self.is_admin = is_admin

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_id = _event_user_id(event)
        if telegram_id is None or not await self.is_admin(telegram_id):
            return await handler(event, data)

        bucket_key = admin_bucket_key(event)
        limit = (
            self.config.sensitive_limit
            if bucket_key in self.config.sensitive_bucket_keys
            else self.config.limit
        )
        async with session_scope() as session:
            allowed, _remaining = await consume_rate_limit_token(
                session,
                scope=self.config.scope,
                identity=str(telegram_id),
                bucket_key=bucket_key,
                limit=limit,
                window_seconds=self.config.window_seconds,
            )
        if not allowed:
            await _answer_throttled(event)
            return None
        return await handler(event, data)


def _command_name(message: Message) -> str | None:
    if not message.text or not message.text.startswith("/"):
        return None
    command = message.text.split(maxsplit=1)[0]
    return command.split("@", maxsplit=1)[0].lower()


def admin_bucket_key(event: TelegramObject) -> str:
    if isinstance(event, Message):
        command = _command_name(event)
        return command.removeprefix("/") if command else "message"
    if isinstance(event, CallbackQuery):
        return admin_callback_bucket_key(event.data)
    return "event"


def admin_callback_bucket_key(data: str | None) -> str:
    if not data:
        return "callback"
    parts = data.split(":")
    if parts[0] == "admin" and len(parts) > 1:
        return f"admin:{parts[1]}"
    return parts[0]


def _event_user_id(event: TelegramObject) -> int | None:
    from_user = getattr(event, "from_user", None)
    return getattr(from_user, "id", None)


async def _answer_throttled(event: TelegramObject) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer(ADMIN_THROTTLED_MESSAGE, show_alert=True)
    elif isinstance(event, Message):
        await event.answer(ADMIN_THROTTLED_MESSAGE)
