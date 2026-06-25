from bot.connection_guides import PLATFORMS, get_app, guides_app_keyboard, guides_apps_keyboard, guides_platforms_keyboard


def test_all_platforms_have_apps():
    assert len(PLATFORMS) == 4
    for platform in PLATFORMS:
        assert len(platform.apps) >= 3


def test_guide_callback_data_fits_telegram_limit():
    keyboards = [guides_platforms_keyboard()]
    for platform in PLATFORMS:
        keyboards.append(guides_apps_keyboard(platform))
        for app in platform.apps:
            keyboards.append(guides_app_keyboard(platform, app))

    for keyboard in keyboards:
        for row in keyboard.inline_keyboard:
            for button in row:
                if button.callback_data:
                    assert len(button.callback_data.encode("utf-8")) <= 64


def test_get_app_returns_guide_steps():
    app = get_app("and", "v2rayng")
    assert app is not None
    assert app.name == "v2rayNG"
    assert len(app.steps) >= 5
    assert app.download_url.startswith("https://")


def test_platforms_cover_android_ios_mac_windows():
    keys = {platform.key for platform in PLATFORMS}
    assert keys == {"and", "ios", "mac", "win"}


def test_guides_apps_keyboard_has_back_to_tutorial():
    keyboard = guides_apps_keyboard(PLATFORMS[0])
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "menu:tutorial" in callbacks
