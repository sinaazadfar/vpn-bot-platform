from bot.db import PurchaseOffer
from bot.discount_flow import discount_error_message, purchase_confirm_text


def test_purchase_confirm_text_shows_coupon_line():
    offer = PurchaseOffer(10, 30, "preset", 5, 100_000, 0, 95_000)
    text = purchase_confirm_text(offer, coupon_percent=15, coupon_code="save15")

    assert "کد تخفیف: SAVE15 (15٪)" in text
    assert "مبلغ نهایی: 95,000 تومان" in text


def test_discount_error_message_maps_known_codes():
    assert "قبلاً" in discount_error_message(ValueError("discount_already_used"))
    assert "مهلت" in discount_error_message(ValueError("discount_expired"))
