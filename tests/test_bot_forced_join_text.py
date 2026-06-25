from bot.db import RequiredChat
from bot.forced_join import forced_join_keyboard, forced_join_text


def test_forced_join_text_single_channel_is_friendly() -> None:
    text = forced_join_text([RequiredChat(1, -100, "کانال VPN", "https://t.me/vpn")])
    assert "سلام" in text
    assert "کانال VPN" in text
    assert "عضو شدم" in text
    assert "عضویت اجباری" not in text


def test_forced_join_keyboard_recheck_label() -> None:
    keyboard = forced_join_keyboard([RequiredChat(1, -100, "کانال VPN", "https://t.me/vpn")], "mybot")
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    labels = [button.text for button in buttons]
    assert "✅ عضو شدم، ادامه بده" in labels
    assert any("عضویت در کانال VPN" in label for label in labels)
    join_button = next(button for button in buttons if button.text == "✅ عضو شدم، ادامه بده")
    assert join_button.url == "https://t.me/mybot?start=joined"
