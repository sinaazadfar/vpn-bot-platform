from __future__ import annotations

import datetime as dt

from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

from bot.context import AppContext
from bot.db import Database, Repository
from bot.middleware.block_check import BlockCheckMiddleware


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
    return CallbackQuery(
        id="cb1",
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        chat_instance="ci",
        data=data,
        message=_message(user_id),
    )


@pytest.mark.asyncio
async def test_blocked_user_cannot_use_wallet_menu(tmp_path):
    database = Database(tmp_path / "block.sqlite3")
    await database.init()
    async with database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user(1001, set(), first_name="Blocked")
        await repository.set_user_blocked(user.id, blocked=True)

    middleware = BlockCheckMiddleware()
    ctx = _ctx({999}, database)
    called = False

    class FakeCallback:
        from_user = User(id=1001, is_bot=False, first_name="Test")
        data = "menu:wallet"
        bot = AsyncMock()

        async def answer(self, *args, **kwargs):
            return None

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, FakeCallback(), {"ctx": ctx})
    assert result is None
    assert called is False


@pytest.mark.asyncio
async def test_blocked_user_can_start(tmp_path):
    database = Database(tmp_path / "block2.sqlite3")
    await database.init()
    async with database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user(1002, set())
        await repository.set_user_blocked(user.id, blocked=True)

    middleware = BlockCheckMiddleware()
    ctx = _ctx({999}, database)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, _message(1002, "/start"), {"ctx": ctx})
    assert result == "ok"
    assert called is True


@pytest.mark.asyncio
async def test_admin_bypasses_block_check(tmp_path):
    database = Database(tmp_path / "block3.sqlite3")
    await database.init()
    middleware = BlockCheckMiddleware()
    ctx = _ctx({1003}, database)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, _callback(1003, "menu:wallet"), {"ctx": ctx})
    assert result == "ok"
    assert called is True
