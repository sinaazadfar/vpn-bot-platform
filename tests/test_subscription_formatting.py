from bot.formatting import html_code, html_link, html_pre
from bot.db import User
from bot.handlers.buyer import _config_text, _configs_text_chunks, _earn_details_text, _earn_invite_instructions, _earn_share_message, _insufficient_wallet_text, _profile_text, _referral_invite_url, _subscription_detail_text, _subscription_link_text
from bot.db import Subscription


def test_html_code_escapes_and_wraps_value():
    assert html_code("vless://host?a=1&b=<x>") == "<code>vless://host?a=1&amp;b=&lt;x&gt;</code>"


def test_html_pre_escapes_and_wraps_value():
    assert html_pre("1. vless://host?a=1&b=<x>") == "<pre>1. vless://host?a=1&amp;b=&lt;x&gt;</pre>"


def test_html_link_escapes_url_and_label():
    assert html_link("شروع <ربات>", "https://t.me/bot?start=A&B") == '<a href="https://t.me/bot?start=A&amp;B">شروع &lt;ربات&gt;</a>'


def test_subscription_link_text_uses_monospace_url():
    text = _subscription_link_text("https://sub.example/user?a=1&b=2")

    assert "لینک اشتراک:" in text
    assert "<code>https://sub.example/user?a=1&amp;b=2</code>" in text


def test_subscription_detail_text_includes_core_fields():
    subscription = Subscription(
        id=42,
        user_id=1,
        plan_id=None,
        marzban_username="user_abc",
        subscription_url="https://sub.example/user",
        expires_at="2026-07-20T00:00:00+00:00",
        traffic_gb=20,
        duration_days=30,
        discount_percent=0,
        base_price=180_000,
        duration_extra=0,
        final_price=180_000,
        purchase_source="manual",
        status="active",
    )
    text = _subscription_detail_text(subscription)

    assert "جزئیات اشتراک" in text
    assert "<code>user_abc</code>" in text
    assert "20 GB" in text
    assert "180,000 تومان" in text
    assert "https://sub.example/user" in text


def test_insufficient_wallet_text_shows_balance_price_and_shortage():
    text = _insufficient_wallet_text(120_000, 250_000)

    assert "موجودی کیف پول کافی نیست." in text
    assert "موجودی کیف پول شما: 120,000 تومان" in text
    assert "مبلغ پلن انتخابی: 250,000 تومان" in text
    assert "مبلغ کسری: 130,000 تومان" in text


def test_config_text_uses_monospace_config():
    text = _config_text(2, "vless://config?x=<tag>&y=1")

    assert text.startswith("کانفیگ 2:")
    assert "<code>vless://config?x=&lt;tag&gt;&amp;y=1</code>" in text


def test_configs_text_chunks_include_all_configs_without_qr_content():
    chunks = _configs_text_chunks(["vless://one", "vmess://two"])
    text = "\n".join(chunks)

    assert "همه کانفیگ‌ها:" in text
    assert "<pre>1. vless://one\n\n2. vmess://two</pre>" in text
    assert "<code>vless://one</code>" not in text


def test_earn_invite_instructions_explains_flow_with_example():
    text = _earn_invite_instructions(15)

    assert "دوستاتو دعوت کن" in text
    assert "خلاصه‌ش اینه" in text
    assert "هر بار که پرداخت کنن" in text
    assert "15٪" in text
    assert "اولین" not in text
    assert "200,000" in text
    assert "30,000 تومن" in text
    assert "این متن رو بفرست" in text
    assert "تمدید" not in text
    assert "https://t.me/" not in text


def test_earn_share_message_includes_bot_name_and_plain_referral_link():
    invite_url = _referral_invite_url("abc123xy", "sellerbot")
    text = _earn_share_message("فروشگاه VPN", invite_url)

    assert text.startswith("سلام!")
    assert "از ربات فروشگاه VPN می‌تونی" in text
    assert "👌👌" in text
    assert invite_url in text
    assert "<a href=" not in text


def test_earn_details_text_contains_personal_stats_and_rules():
    text = _earn_details_text("abc123xy", 15, 250_000)

    assert "<code>ABC123XY</code>" in text
    assert "پورسانت فعلی: 15٪ از هر پرداخت" in text
    assert "تا الان دراوردی: 250,000 تومن" in text
    assert "لینک دعوت تو" in text
    assert "کیف پولت" in text
    assert "تمدید" not in text


def test_profile_text_shows_core_fields_and_hides_referral_when_earning_disabled():
    user = User(id=1, telegram_id=123456, role="buyer", wallet_balance=250_000, referral_code="abc123xy", referred_by=None)

    text = _profile_text(user, subscription_count=3, earning_enabled=False)

    assert "حساب کاربری" in text
    assert "شناسه تلگرام: 123456" in text
    assert "نقش: کاربر" in text
    assert "موجودی کیف پول: 250,000 تومان" in text
    assert "تعداد اشتراک‌ها: 3" in text
    assert "کد دعوت" not in text
    assert "درآمد ثبت‌شده" not in text


def test_profile_text_shows_referral_when_earning_enabled():
    user = User(id=1, telegram_id=123456, role="admin", wallet_balance=0, referral_code="abc123xy", referred_by=None)

    text = _profile_text(user, subscription_count=0, earning_enabled=True, referral_total=50_000)

    assert "نقش: ادمین" in text
    assert "درآمد ثبت‌شده: 50,000 تومان" in text
    assert "کد دعوت: <code>ABC123XY</code>" in text
