from __future__ import annotations

from dataclasses import dataclass

MAX_CALLBACK_DATA_BYTES = 64


@dataclass(frozen=True)
class CallbackAction:
    scope: str
    action: str
    value: str | None = None


def build_callback(scope: str, action: str, value: str | None = None) -> str:
    parts = [scope, action]
    if value:
        parts.append(value)
    callback_data = ":".join(parts)
    if len(callback_data.encode("utf-8")) > MAX_CALLBACK_DATA_BYTES:
        raise ValueError("callback_data_too_long")
    return callback_data


def parse_callback(callback_data: str) -> CallbackAction:
    parts = callback_data.split(":", maxsplit=2)
    if len(parts) < 2:
        raise ValueError("invalid_callback_data")
    return CallbackAction(
        scope=parts[0],
        action=parts[1],
        value=parts[2] if len(parts) == 3 else None,
    )
