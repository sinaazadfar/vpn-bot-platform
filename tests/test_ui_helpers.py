from __future__ import annotations

import pytest

from vpn_bot_platform.common.ui.callbacks import build_callback, parse_callback
from vpn_bot_platform.common.ui.keyboards import (
    admin_payment_actions,
    admin_ticket_actions,
    admin_wallet_charge_actions,
    master_main_menu,
    seller_admin_menu,
    seller_buyer_menu,
)
from vpn_bot_platform.common.ui.messages import status_label


def test_callback_round_trip() -> None:
    callback_data = build_callback("s", "buy", "abc123")

    action = parse_callback(callback_data)

    assert action.scope == "s"
    assert action.action == "buy"
    assert action.value == "abc123"


def test_callback_rejects_too_long_data() -> None:
    with pytest.raises(ValueError, match="callback_data_too_long"):
        build_callback("s", "buy", "x" * 100)


def test_main_menus_have_buttons() -> None:
    assert master_main_menu().inline_keyboard
    assert seller_buyer_menu().inline_keyboard
    assert seller_admin_menu().inline_keyboard


def test_admin_action_keyboards_fit_callback_limit() -> None:
    uuid = "12345678-1234-1234-1234-123456789abc"

    for keyboard in (
        admin_payment_actions(uuid),
        admin_wallet_charge_actions(uuid),
        admin_ticket_actions(uuid),
    ):
        for row in keyboard.inline_keyboard:
            for button in row:
                assert button.callback_data is not None
                assert len(button.callback_data.encode("utf-8")) <= 64


def test_status_label_is_stable() -> None:
    assert status_label("active") == "[OK] Active"
    assert status_label("waiting_payment") == "[...] Waiting Payment"
