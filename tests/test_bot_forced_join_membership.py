from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberLeft, ChatMemberMember, User

from bot.db import RequiredChat
from bot.forced_join import (
    evaluate_forced_join,
    is_active_chat_member,
    is_user_member_of_chat,
    required_chat_targets,
)


def _user() -> User:
    return User(id=42, is_bot=False, first_name="Test")


def test_required_chat_targets_includes_username_from_invite_link() -> None:
    chat = RequiredChat(1, -100123, "VPN", "https://t.me/myvpnchannel")
    assert required_chat_targets(chat) == [-100123, "@myvpnchannel"]


def test_is_active_chat_member_accepts_member_types() -> None:
    user = _user()
    assert is_active_chat_member(ChatMemberMember(status=ChatMemberStatus.MEMBER, user=user)) is True
    assert is_active_chat_member(ChatMemberLeft(status=ChatMemberStatus.LEFT, user=user)) is False


@pytest.mark.asyncio
async def test_is_user_member_of_chat_tries_username_fallback() -> None:
    chat = RequiredChat(1, -100123, "VPN", "https://t.me/myvpnchannel")
    bot = AsyncMock()
    bot.get_chat_member = AsyncMock(
        side_effect=[
            TelegramAPIError(method=None, message="bad id"),
            ChatMemberMember(status=ChatMemberStatus.MEMBER, user=_user()),
        ]
    )
    joined, error = await is_user_member_of_chat(bot, chat, 42)
    assert joined is True
    assert error is None
    assert bot.get_chat_member.await_count == 2


@pytest.mark.asyncio
async def test_evaluate_forced_join_reports_verify_error() -> None:
    chat = RequiredChat(1, -100123, "VPN", "https://t.me/myvpnchannel")
    bot = AsyncMock()
    bot.get_chat_member = AsyncMock(side_effect=TelegramAPIError(method=None, message="no access"))
    allowed, reason = await evaluate_forced_join(bot, 42, [chat])
    assert allowed is False
    assert reason == "verify_error"
