from bot.handlers.admin import _earning_settings_text


def test_earning_settings_text_explains_status_percent_and_payment_rule():
    text = _earning_settings_text(True, 12)

    assert "تنظیمات کسب درآمد" in text
    assert "وضعیت: فعال" in text
    assert "پورسانت هر پرداخت: 12٪" in text
    assert "هر خرید یا تمدید" in text
