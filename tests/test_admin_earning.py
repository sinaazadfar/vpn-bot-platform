from bot.handlers.admin import _earning_settings_text


def test_earning_settings_text_explains_status_percent_and_extension_rule():
    text = _earning_settings_text(True, 12)

    assert "تنظیمات کسب درآمد" in text
    assert "وضعیت: فعال" in text
    assert "پورسانت خرید جدید: 12٪" in text
    assert "تمدید اشتراک پورسانت ندارد" in text
