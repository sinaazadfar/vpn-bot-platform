from __future__ import annotations

import pytest

from vpn_bot_platform.common.ui.callbacks import build_callback, parse_callback
from vpn_bot_platform.common.ui.keyboards import (
    admin_order_actions,
    admin_customer_card_actions,
    admin_customer_detail_actions,
    admin_customers_menu,
    admin_payment_actions,
    admin_ticket_actions,
    admin_wallet_charge_actions,
    broadcast_actions,
    confirm_keyboard,
    discount_actions,
    external_template_actions,
    extra_volume_confirm_menu,
    extra_volume_coupon_menu,
    extra_volume_plan_button,
    forced_join_blocked_menu,
    forced_join_menu,
    master_main_menu,
    master_reply_menu,
    master_section_menu,
    master_seller_bot_actions,
    paginate,
    pagination_row,
    payment_request_actions,
    panel_actions,
    plan_actions,
    plan_buy_button,
    purchase_confirm_menu,
    purchase_coupon_menu,
    renewal_confirm_menu,
    renewal_coupon_menu,
    renewal_plan_button,
    reseller_actions,
    reseller_card_actions,
    reseller_detail_actions,
    reseller_list_menu,
    seller_section_menu,
    service_actions,
    seller_admin_reply_menu,
    seller_admin_menu,
    seller_buyer_reply_menu,
    seller_buyer_menu,
    seller_report_menu,
    support_menu,
    wallet_charge_menu,
    wallet_transaction_actions,
)
from vpn_bot_platform.common.ui.messages import status_label


def _assert_callback_data_fits(keyboard) -> None:
    for row in keyboard.inline_keyboard:
        for button in row:
            assert button.callback_data is not None
            assert len(button.callback_data.encode("utf-8")) <= 64


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
    assert master_seller_bot_actions("12345678-1234-1234-1234-123456789abc").inline_keyboard
    assert external_template_actions("12345678-1234-1234-1234-123456789abc").inline_keyboard
    assert reseller_list_menu(page=1, total_pages=3).inline_keyboard
    assert panel_actions("12345678-1234-1234-1234-123456789abc").inline_keyboard
    assert reseller_card_actions(12345).inline_keyboard
    assert reseller_detail_actions(12345).inline_keyboard
    assert seller_buyer_menu().inline_keyboard
    assert seller_admin_menu().inline_keyboard
    assert seller_report_menu().inline_keyboard
    assert wallet_charge_menu().inline_keyboard
    assert support_menu().inline_keyboard
    assert forced_join_menu().inline_keyboard
    assert forced_join_blocked_menu().inline_keyboard
    assert master_reply_menu().keyboard
    assert seller_buyer_reply_menu().keyboard
    assert seller_admin_reply_menu().keyboard


def test_inline_keyboards_fit_callback_limit() -> None:
    uuid = "12345678-1234-1234-1234-123456789abc"

    for keyboard in (
        master_main_menu(),
        master_section_menu("resellers"),
        master_section_menu("seller_bots"),
        master_section_menu("external_bots"),
        master_section_menu("panels"),
        master_section_menu("plans"),
        master_section_menu("discounts"),
        master_section_menu("broadcasts"),
        master_section_menu("settings"),
        master_section_menu("system"),
        reseller_actions(123456789),
        reseller_list_menu(page=1, total_pages=3),
        reseller_card_actions(123456789),
        reseller_detail_actions(123456789),
        panel_actions(uuid),
        plan_actions(uuid),
        plan_actions(uuid, is_active=False),
        discount_actions(uuid),
        discount_actions(uuid, is_active=False),
        broadcast_actions(uuid),
        broadcast_actions(uuid, status="sent"),
        forced_join_menu(),
        forced_join_blocked_menu(),
        master_seller_bot_actions(uuid),
        external_template_actions(uuid),
        seller_buyer_menu(),
        seller_admin_menu(),
        seller_report_menu(),
        seller_section_menu("wallet"),
        payment_request_actions(uuid),
        plan_buy_button(uuid),
        purchase_coupon_menu(),
        purchase_confirm_menu(),
        renewal_plan_button(uuid),
        renewal_coupon_menu(),
        renewal_confirm_menu(),
        extra_volume_plan_button(uuid),
        extra_volume_coupon_menu(),
        extra_volume_confirm_menu(),
        service_actions(uuid),
        wallet_charge_menu(),
        wallet_transaction_actions(uuid),
        support_menu(),
        admin_customers_menu(),
        admin_payment_actions(uuid),
        admin_customers_menu(),
        admin_customer_card_actions(uuid),
        admin_customer_detail_actions(uuid),
        admin_order_actions(uuid),
        admin_order_actions(uuid, renewal=True),
        admin_order_actions(uuid, extra_volume=True),
        admin_wallet_charge_actions(uuid),
        admin_ticket_actions(uuid),
        confirm_keyboard(scope="m", confirm_action="ok", cancel_action="cancel", value=uuid),
    ):
        _assert_callback_data_fits(keyboard)


def test_confirm_keyboard_has_confirm_and_cancel() -> None:
    keyboard = confirm_keyboard(
        scope="m",
        confirm_action="ok",
        cancel_action="cancel",
        value="123",
    )

    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert callbacks == ["m:ok:123", "m:cancel:123"]


def test_pagination_helper_clamps_pages() -> None:
    page = paginate(list(range(25)), page=9, per_page=10)

    assert page.page == 3
    assert page.total_pages == 3
    assert page.items == [20, 21, 22, 23, 24]
    assert pagination_row(scope="m", action="resellers", page=2, total_pages=3) == [
        ("قبلی", "m:resellers:1"),
        ("2/3", "m:resellers:2"),
        ("بعدی", "m:resellers:3"),
    ]


def test_status_label_is_stable() -> None:
    assert status_label("active") == "[OK] Active"
    assert status_label("waiting_payment") == "[...] Waiting Payment"
    assert status_label("paid") == "[OK] Paid"
