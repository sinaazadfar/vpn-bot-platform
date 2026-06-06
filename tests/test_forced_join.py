from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine
from vpn_bot_platform.common.forced_join import (
    ForcedJoinChat,
    decode_forced_join_chats,
    encode_forced_join_chats,
)
from vpn_bot_platform.master_bot.services.resellers import ResellerService


def test_forced_join_codec_round_trip() -> None:
    encoded = encode_forced_join_chats([ForcedJoinChat(chat_id="@channel", title="Channel")])

    assert decode_forced_join_chats(encoded) == [ForcedJoinChat(chat_id="@channel", title="Channel")]


@pytest.mark.asyncio
async def test_master_service_stores_forced_join_chats() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await service.set_forced_join_chats(
            chats=[ForcedJoinChat(chat_id="@channel", title="Channel")]
        )
        chats = await service.get_forced_join_chats()
    finally:
        await dispose_engine()

    assert chats == [ForcedJoinChat(chat_id="@channel", title="Channel")]

