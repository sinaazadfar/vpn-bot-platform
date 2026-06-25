from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

from bot.context import AppContext
from bot.db import Database, Repository
from bot.middleware.forced_join import ForcedJoinMiddleware


def _ctx(admin_ids: set[int], db: Database) -> AppContext:
    from bot.config import Settings
    from bot.marzban import MarzbanClient
    from bot.quota import MasterVolumeQuota

    settings = Settings.model_construct(
        bot_token="test:token",
        admin_ids_raw=",".join(str(item) for item in sorted(admin_ids)),
        database_path=db.path,
        marzban_base_url="http://localhost",
        marzban_username="",
        marzban_password="",
        marzban_token="",
        marzban_default_proxies_json="{}",
        web_app_url="",
        platform_database_url="",
        seller_bot_id="",
    )
    return AppContext(
        settings=settings,
        database=db,
        marzban=MarzbanClient("", "", "", "", "{}"),
        quota=MasterVolumeQuota(platform_database_url="", seller_bot_id=""),
    )


def _message(user_id: int, text: str = "/start") -> Message:
    return Message(
        message_id=1,
        date=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        chat=Chat(id=user_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        text=text,
    )


def _callback(user_id: int, data: str) -> CallbackQuery:
    message = _message(user_id)
    return CallbackQuery(
        id="cb1",
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        chat_instance="ci",
        data=data,
        message=message,
    )


@pytest.mark.asyncio
async def test_forced_join_blocks_start_when_not_member(tmp_path) -> None:
    database = Database(tmp_path / "join.sqlite3")
    await database.init()
    async with database.session() as db:
        await Repository(db).add_required_chat(-100111, "Test Channel", "https://t.me/testchannel")

    middleware = ForcedJoinMiddleware()
    ctx = _ctx({999}, database)

    class FakeMessage:
        from_user = User(id=1001, is_bot=False, first_name="Test")
        text = "/start"
        bot = AsyncMock()

        async def answer(self, *args, **kwargs):
            return None

    message = FakeMessage()
    message.bot.get_chat_member = AsyncMock(return_value=AsyncMock(status="left"))

    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, message, {"ctx": ctx})
    assert result is None
    assert called is False
    message.bot.get_chat_member.assert_awaited()


@pytest.mark.asyncio
async def test_forced_join_allows_member(tmp_path) -> None:
    database = Database(tmp_path / "join2.sqlite3")
    await database.init()
    async with database.session() as db:
        await Repository(db).add_required_chat(-100111, "Test Channel", "https://t.me/testchannel")

    middleware = ForcedJoinMiddleware()
    ctx = _ctx({999}, database)

    class FakeMessage:
        from_user = User(id=1001, is_bot=False, first_name="Test")
        text = "/start"
        bot = AsyncMock()

    message = FakeMessage()
    message.bot.get_chat_member = AsyncMock(return_value=AsyncMock(status="member"))

    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, message, {"ctx": ctx})
    assert result == "ok"
    assert called is True


@pytest.mark.asyncio
async def test_forced_join_update_object_is_not_checked(tmp_path) -> None:
    from aiogram.types import Update

    database = Database(tmp_path / "join3.sqlite3")
    await database.init()
    middleware = ForcedJoinMiddleware()
    ctx = _ctx({999}, database)
    update = Update(
        update_id=1,
        message=_message(1001, "/start"),
    )
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, update, {"ctx": ctx})
    assert result == "ok"
    assert called is True
