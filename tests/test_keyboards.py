from bot import constants as c
from bot.keyboards import MAX_WALLET_TOP_UP, MIN_WALLET_TOP_UP, WALLET_TOP_UP_AMOUNTS, admin_back_keyboard, admin_discount_max_uses_keyboard, admin_discount_valid_days_keyboard, admin_earning_keyboard, admin_menu, earn_details_keyboard, earn_keyboard, main_menu, payment_review_keyboard, profile_keyboard, purchase_coupon_keyboard, subscription_back_keyboard, subscription_configs_keyboard, subscription_detail_keyboard, traffic_presets_keyboard, wallet_payment_keyboard, wallet_top_up_keyboard
from bot.db import TrafficPreset


def test_wallet_top_up_keyboard_has_two_column_presets():
    keyboard = wallet_top_up_keyboard()

    first_rows = keyboard.inline_keyboard[:2]
    callbacks = [
        button.callback_data
        for row in first_rows
        for button in row
    ]

    assert all(len(row) == 2 for row in first_rows)
    assert callbacks == [f"wallet:amount:{amount}" for amount in WALLET_TOP_UP_AMOUNTS]


def test_wallet_top_up_keyboard_has_manual_and_back():
    keyboard = wallet_top_up_keyboard()

    assert keyboard.inline_keyboard[2][0].callback_data == "wallet:manual"
    assert keyboard.inline_keyboard[3][0].callback_data == "wallet:ledger:1"
    assert keyboard.inline_keyboard[4][0].callback_data == "menu:home"
    assert keyboard.inline_keyboard[4][1].callback_data == "menu:support"


def test_wallet_top_up_keyboard_support_uses_url_when_configured():
    keyboard = wallet_top_up_keyboard("Support_User")
    support_button = keyboard.inline_keyboard[4][1]

    assert support_button.url == "https://t.me/Support_User"
    assert support_button.callback_data is None


def test_wallet_payment_keyboard_has_back_and_support():
    keyboard = wallet_payment_keyboard("Support_User")

    assert keyboard.inline_keyboard[0][0].callback_data == "menu:wallet"
    assert keyboard.inline_keyboard[0][1].url == "https://t.me/Support_User"


def test_wallet_top_up_presets_fit_manual_bounds():
    assert MIN_WALLET_TOP_UP == 50_000
    assert MAX_WALLET_TOP_UP == 3_000_000
    assert all(MIN_WALLET_TOP_UP <= amount <= MAX_WALLET_TOP_UP for amount in WALLET_TOP_UP_AMOUNTS)


def test_subscription_detail_keyboard_uses_persian_labels_and_configs_submenu():
    keyboard = subscription_detail_keyboard(42)
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    labels = {button.text for button in buttons}
    callbacks = {button.callback_data for button in buttons}

    assert {
        "QR اشتراک",
        "لینک اشتراک",
        "دریافت کانفیگ‌ها",
        "تغییر لینک اشتراک",
        "تمدید اشتراک",
        "آموزش اتصال",
    }.issubset(labels)
    assert "sub:configs:42" in callbacks
    assert "menu:tutorial" in callbacks


def test_subscriptions_page_keyboard_has_inline_search_and_status_emoji():
    from bot.db import Subscription
    from bot.keyboards import subscriptions_page_keyboard

    subscriptions = [
        Subscription(
            id=1,
            user_id=1,
            plan_id=None,
            marzban_username="sub_alpha",
            subscription_url="https://panel.example/sub/alpha",
            expires_at="2026-07-20T00:00:00+00:00",
            traffic_gb=10,
            duration_days=30,
            discount_percent=0,
            base_price=100_000,
            duration_extra=0,
            final_price=100_000,
            purchase_source="manual",
            status="active",
        )
    ]
    keyboard = subscriptions_page_keyboard(subscriptions, page=1, total_pages=1)
    search_button = next(button for row in keyboard.inline_keyboard for button in row if button.text == "🔎 جستجو")

    assert search_button.switch_inline_query_current_chat == "subs:"
    assert keyboard.inline_keyboard[0][0].text.startswith("🟢")


def test_subscription_configs_keyboard_lists_config_actions():
    keyboard = subscription_configs_keyboard(42)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert "sub:configs_link:42" in callbacks
    assert "sub:configs_all:42" in callbacks
    assert "sub:configs_txt:42" in callbacks
    assert "sub:detail:42" in callbacks


def test_earn_keyboards_have_details_invite_and_back_actions():
    invite_keyboard = earn_keyboard()
    details_keyboard = earn_details_keyboard()

    assert invite_keyboard.inline_keyboard[0][0].text == "جزئیات درآمد"
    assert invite_keyboard.inline_keyboard[0][0].callback_data == "earn:details"
    assert invite_keyboard.inline_keyboard[1][0].callback_data == "menu:home"
    assert details_keyboard.inline_keyboard[0][0].callback_data == "menu:earn"
    assert details_keyboard.inline_keyboard[1][0].callback_data == "menu:home"


def test_main_menu_layout_and_hides_earn_when_disabled():
    disabled_keyboard = main_menu(False, earning_enabled=False)
    enabled_keyboard = main_menu(False, earning_enabled=True)
    disabled_labels = [button.text for row in disabled_keyboard.inline_keyboard for button in row]
    enabled_labels = [button.text for row in enabled_keyboard.inline_keyboard for button in row]

    assert disabled_keyboard.inline_keyboard[0][0].text == c.BUY_SUBSCRIPTION
    assert disabled_keyboard.inline_keyboard[1][0].text == c.WALLET
    assert disabled_keyboard.inline_keyboard[1][1].text == c.PROFILE
    assert disabled_keyboard.inline_keyboard[2][0].text == c.MY_SUBSCRIPTIONS
    assert disabled_keyboard.inline_keyboard[3][0].text == c.TUTORIAL
    assert disabled_keyboard.inline_keyboard[4][0].text == c.SUPPORT
    assert disabled_keyboard.inline_keyboard[4][1].text == "تیکت"
    assert c.EARN not in disabled_labels
    assert "تست رایگان" not in disabled_labels
    assert c.EARN in enabled_labels
    assert enabled_keyboard.inline_keyboard[3][0].text == c.EARN
    assert enabled_keyboard.inline_keyboard[3][1].text == c.TUTORIAL


def test_admin_earning_keyboard_has_toggle_percent_and_back():
    keyboard = admin_earning_keyboard(True, 12)

    assert keyboard.inline_keyboard[0][0].text == "وضعیت: فعال"
    assert keyboard.inline_keyboard[0][0].callback_data == "earning:toggle"
    assert keyboard.inline_keyboard[1][0].text == "پورسانت: 12٪"
    assert keyboard.inline_keyboard[1][0].callback_data == "earning:set_percent"
    assert keyboard.inline_keyboard[2][0].callback_data == "admin:panel"


def test_admin_menu_has_quota_button():
    keyboard = admin_menu()
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert c.ADMIN_QUOTA in labels
    assert "admin:quota" in callbacks
    assert "admin:tickets" in callbacks
    assert "admin:sales" in callbacks


def test_admin_back_keyboard_returns_to_admin_panel():
    keyboard = admin_back_keyboard()

    assert keyboard.inline_keyboard[0][0].text == c.BACK
    assert keyboard.inline_keyboard[0][0].callback_data == "admin:panel"


def test_subscription_back_keyboard_returns_to_subscription_detail():
    keyboard = subscription_back_keyboard(42)

    assert keyboard.inline_keyboard[0][0].text == c.BACK
    assert keyboard.inline_keyboard[0][0].callback_data == "sub:detail:42"


def test_payment_review_keyboard_has_actions_and_back():
    keyboard = payment_review_keyboard(7)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert "pay_ok:7" in callbacks
    assert "pay_no:7" in callbacks
    assert "admin:payments" in callbacks


def test_profile_keyboard_has_actions_and_hides_earn_when_disabled():
    keyboard = profile_keyboard()
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert c.WALLET in labels
    assert c.MY_SUBSCRIPTIONS in labels
    assert c.SUPPORT in labels
    assert c.BACK in labels
    assert c.EARN not in labels
    assert "menu:wallet" in callbacks
    assert "menu:subs" in callbacks
    assert "menu:support" in callbacks
    assert "menu:home" in callbacks


def test_profile_keyboard_shows_earn_and_support_callbacks():
    keyboard = profile_keyboard(earning_enabled=True)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    support_button = next(button for row in keyboard.inline_keyboard for button in row if button.text == c.SUPPORT)
    ticket_button = next(button for row in keyboard.inline_keyboard for button in row if button.text == "تیکت")

    assert c.EARN in labels
    assert support_button.callback_data == "menu:support"
    assert ticket_button.callback_data == "menu:tickets"


def test_traffic_presets_keyboard_shows_trial_button_when_enabled():
    presets = [TrafficPreset(id=1, gb=10, discount_percent=0, active=True)]
    without_trial = traffic_presets_keyboard(presets)
    with_trial = traffic_presets_keyboard(presets, show_trial=True)

    without_callbacks = [button.callback_data for row in without_trial.inline_keyboard for button in row]
    with_callbacks = [button.callback_data for row in with_trial.inline_keyboard for button in row]

    assert "menu:trial" not in without_callbacks
    assert with_trial.inline_keyboard[0][0].text == "🎁 تست رایگان"
    assert with_trial.inline_keyboard[0][0].callback_data == "menu:trial"
    assert "menu:trial" in with_callbacks


def test_purchase_coupon_keyboard_has_enter_skip_and_back():
    keyboard = purchase_coupon_keyboard(10, 30, "preset", 5)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert "coupon:ask:30:10:preset:5" in callbacks
    assert "coupon:skip:30:10:preset:5" in callbacks
    assert "menu:buy" in callbacks


def test_admin_discount_unlimited_keyboards():
    max_uses = admin_discount_max_uses_keyboard()
    valid_days = admin_discount_valid_days_keyboard()

    assert max_uses.inline_keyboard[0][0].callback_data == "discount:max_uses:0"
    assert max_uses.inline_keyboard[0][0].text == "♾️ نامحدود"
    assert valid_days.inline_keyboard[0][0].callback_data == "discount:valid_days:0"
    assert valid_days.inline_keyboard[0][0].text == "♾️ نامحدود"
