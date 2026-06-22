from bot.formatting import html_code, html_link, html_pre
from bot.db import User
from bot.handlers.buyer import _config_text, _configs_text_chunks, _earn_details_text, _earn_invite_text, _insufficient_wallet_text, _profile_text, _referral_invite_url, _subscription_link_text


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


def test_earn_invite_text_uses_uppercase_monospace_code_and_link():
    invite_url = _referral_invite_url("abc123xy", "sellerbot")
    text = _earn_invite_text(invite_url)

    assert "دعوت دوستان و کسب درآمد" in text
    assert "درآمد ثبت‌شده" not in text
    assert "پورسانت شما" not in text
    assert "کد دعوت" not in text
    assert "<code>ABC123XY</code>" not in text
    assert '<a href="https://t.me/sellerbot?start=ABC123XY">ورود با لینک رفرال</a>' in text
    assert "<code>https://t.me/sellerbot?start=ABC123XY</code>" not in text


def test_earn_details_text_contains_personal_stats_and_rules():
    text = _earn_details_text("abc123xy", 15, 250_000)

    assert "<code>ABC123XY</code>" in text
    assert "پورسانت فعلی: 15٪" in text
    assert "درآمد ثبت‌شده شما: 250,000 تومان" in text
    assert "یک‌سطحی" in text
    assert "کیف پول" in text
    assert "تمدید اشتراک شامل پورسانت نیست" in text


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
