from __future__ import annotations

import json
from dataclasses import dataclass

FORCED_JOIN_CHATS_KEY = "forced_join_chats"


@dataclass(frozen=True)
class ForcedJoinChat:
    chat_id: str
    title: str | None = None


def encode_forced_join_chats(chats: list[ForcedJoinChat]) -> str:
    return json.dumps([chat.__dict__ for chat in chats], ensure_ascii=True)


def decode_forced_join_chats(value: str | None) -> list[ForcedJoinChat]:
    if not value:
        return []
    raw = json.loads(value)
    return [
        ForcedJoinChat(chat_id=str(item["chat_id"]), title=item.get("title"))
        for item in raw
        if isinstance(item, dict) and item.get("chat_id")
    ]

