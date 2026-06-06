from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from vpn_bot_platform.common.db import session_scope
from vpn_bot_platform.common.repositories import consume_rate_limit_token


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


def _command_name(message: Message) -> str | None:
    if not message.text or not message.text.startswith("/"):
        return None
    command = message.text.split(maxsplit=1)[0]
    return command.split("@", maxsplit=1)[0].lower()
