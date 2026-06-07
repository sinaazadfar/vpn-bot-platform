from __future__ import annotations

from vpn_bot_platform.master_bot.handlers.basic import _parse_args


def test_master_command_parser_accepts_quoted_names() -> None:
    assert _parse_args('252486544 "Sina Azad" 123:token') == [
        "252486544",
        "Sina Azad",
        "123:token",
    ]


def test_master_command_parser_returns_empty_list_for_bad_quotes() -> None:
    assert _parse_args('252486544 "Sina Azad') == []
