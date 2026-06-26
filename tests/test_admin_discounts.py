from bot.admin_discounts import (
    admin_discount_detail_keyboard,
    admin_discounts_list_keyboard,
    discount_detail_text,
    discount_list_line,
)
from bot.db import DiscountCode


def _code(**kwargs) -> DiscountCode:
    defaults = {
        "id": 1,
        "code": "save20",
        "discount_percent": 20,
        "max_uses": 5,
        "used_count": 2,
        "active": True,
        "expires_at": "2026-12-31T00:00:00+00:00",
    }
    defaults.update(kwargs)
    return DiscountCode(**defaults)


def test_discount_list_line_shows_status_and_usage():
    assert "SAVE20" in discount_list_line(_code())
    assert "2/5" in discount_list_line(_code())
    assert "⛔" in discount_list_line(_code(active=False))


def test_discount_detail_text_contains_fields():
    text = discount_detail_text(_code())

    assert "SAVE20" in text
    assert "20٪" in text
    assert "فعال" in text


def test_admin_discounts_list_keyboard_links_to_detail():
    keyboard = admin_discounts_list_keyboard([_code(id=7)])

    assert keyboard.inline_keyboard[0][0].callback_data == "discount:view:7"


def test_admin_discount_detail_keyboard_has_edit_and_delete():
    keyboard = admin_discount_detail_keyboard(7)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert "discount:edit:7:percent" in callbacks
    assert "discount:edit:7:max_uses" in callbacks
    assert "discount:edit:7:valid_days" in callbacks
    assert "discount:del:7" in callbacks
