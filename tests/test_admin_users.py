import pytest
import pytest_asyncio

from bot.admin_users import USERS_PER_PAGE, admin_users_list_keyboard, user_button_title, user_display_name, users_total_pages, wallet_admin_adjustment_user_text
from bot.db import Database, Repository


@pytest_asyncio.fixture
async def repository(tmp_path):
    database = Database(tmp_path / "admin-users.sqlite3")
    await database.init()
    async with database.session() as db:
        yield Repository(db)


@pytest.mark.asyncio
async def test_count_users_and_pagination(repository):
    for telegram_id in (1001, 1002, 1003, 1004, 1005):
        await repository.ensure_user(telegram_id, set())
    assert await repository.count_users() == 5
    page1 = await repository.list_users_page(page=1, per_page=2)
    page2 = await repository.list_users_page(page=2, per_page=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].telegram_id != page2[0].telegram_id


@pytest.mark.asyncio
async def test_search_users_by_telegram_id(repository):
    user = await repository.ensure_user(99887766, set())
    results = await repository.search_users("998877")
    assert len(results) == 1
    assert results[0].id == user.id


@pytest.mark.asyncio
async def test_search_users_by_referral_code(repository):
    user = await repository.ensure_user(10001, set())
    results = await repository.search_users(user.referral_code[:4])
    assert any(item.id == user.id for item in results)


@pytest.mark.asyncio
async def test_search_users_by_username(repository):
    user = await repository.ensure_user(10003, set(), first_name="Ali", username="alitest")
    results = await repository.search_users("@alitest")
    assert len(results) == 1
    assert results[0].id == user.id


@pytest.mark.asyncio
async def test_search_users_by_first_name(repository):
    await repository.ensure_user(10004, set(), first_name="Sina", last_name="Azad")
    results = await repository.search_users("sina")
    assert len(results) == 1
    assert results[0].first_name == "Sina"


@pytest.mark.asyncio
async def test_search_users_by_last_name(repository):
    await repository.ensure_user(10006, set(), first_name="Sina", last_name="Azadfar")
    results = await repository.search_users("Azadfar")
    assert len(results) == 1
    assert results[0].last_name == "Azadfar"


@pytest.mark.asyncio
async def test_search_users_by_full_name(repository):
    user = await repository.ensure_user(10007, set(), first_name="Ali", last_name="Karimi")
    results = await repository.search_users("Ali Karimi")
    assert len(results) == 1
    assert results[0].id == user.id


def test_user_button_title_shows_full_name():
    from bot.admin_users import _user_button_label
    from bot.db import User

    user = User(
        id=1,
        telegram_id=12345,
        role="buyer",
        wallet_balance=50_000,
        referral_code="abc",
        referred_by=None,
        first_name="Ali",
        last_name="Reza",
        username="alireza",
    )
    assert user_button_title(user) == "Ali Reza"
    assert "@alireza" not in _user_button_label(user)
    assert "Ali Reza" in _user_button_label(user)


def test_user_display_name_prefers_name_and_username():
    from bot.db import User

    user = User(
        id=1,
        telegram_id=12345,
        role="buyer",
        wallet_balance=0,
        referral_code="abc",
        referred_by=None,
        first_name="Ali",
        last_name="Reza",
        username="alireza",
    )
    assert user_display_name(user) == "Ali Reza · @alireza"


def test_user_display_name_username_only():
    from bot.db import User

    user = User(
        id=1,
        telegram_id=12345,
        role="buyer",
        wallet_balance=0,
        referral_code="abc",
        referred_by=None,
        username="onlyuser",
    )
    assert user_display_name(user) == "@onlyuser"


@pytest.mark.asyncio
async def test_ensure_user_updates_profile(repository):
    user = await repository.ensure_user(10005, set(), first_name="Old")
    updated = await repository.ensure_user(10005, set(), first_name="New", username="newuser")
    assert updated.id == user.id
    assert updated.first_name == "New"
    assert updated.username == "newuser"


@pytest.mark.asyncio
async def test_sync_telegram_profile(repository):
    user = await repository.ensure_user(10008, set())
    updated = await repository.sync_telegram_profile(
        user.telegram_id,
        first_name="Fetched",
        last_name="Name",
        username="fetcheduser",
    )
    assert updated is not None
    assert updated.first_name == "Fetched"
    assert updated.last_name == "Name"
    assert updated.username == "fetcheduser"


@pytest.mark.asyncio
async def test_sync_telegram_profile_skips_none_values(repository):
    user = await repository.ensure_user(10009, set(), first_name="Keep", username="keepme")
    updated = await repository.sync_telegram_profile(user.telegram_id, first_name=None, last_name="New", username=None)
    assert updated is not None
    assert updated.first_name == "Keep"
    assert updated.last_name == "New"
    assert updated.username == "keepme"


def test_user_needs_profile_sync():
    from bot.db import User
    from bot.user_profile import user_needs_profile_sync

    assert user_needs_profile_sync(
        User(1, 1, "buyer", 0, "abc", None, first_name=None, last_name=None, username="x")
    )
    assert not user_needs_profile_sync(
        User(1, 1, "buyer", 0, "abc", None, first_name="Ali", last_name=None, username=None)
    )


@pytest.mark.asyncio
async def test_set_user_blocked(repository):
    user = await repository.ensure_user(10002, set())
    blocked = await repository.set_user_blocked(user.id, blocked=True)
    assert blocked is not None
    assert blocked.is_blocked is True
    unblocked = await repository.set_user_blocked(user.id, blocked=False)
    assert unblocked is not None
    assert unblocked.is_blocked is False


@pytest.mark.asyncio
async def test_cannot_block_admin_user(repository):
    admin = await repository.ensure_user(90001, {90001})
    assert admin.role == "admin"
    result = await repository.set_user_blocked(admin.id, blocked=True)
    assert result is None


def test_wallet_admin_adjustment_user_text_credit():
    text = wallet_admin_adjustment_user_text(amount=100_000, balance=250_000)
    assert "100,000" in text
    assert "250,000" in text
    assert "شارژ کیف پول" in text


def test_wallet_admin_adjustment_user_text_debit():
    text = wallet_admin_adjustment_user_text(amount=-50_000, balance=200_000)
    assert "50,000" in text
    assert "کسر شد" in text


def test_users_total_pages():
    assert users_total_pages(0) == 1
    assert users_total_pages(1) == 1
    assert users_total_pages(USERS_PER_PAGE) == 1
    assert users_total_pages(USERS_PER_PAGE + 1) == 2


@pytest.mark.asyncio
async def test_search_users_by_marzban_username(repository):
    user = await repository.ensure_user(10010, set())
    settings = await repository.update_pricing_settings(per_gb_price=10_000)
    offer = repository.build_offer(settings, 10, 30, "manual")
    await repository.adjust_wallet(user.id, 500_000, "seed")
    await repository.db.commit()
    user = await repository.get_user_by_telegram_id(10010)
    await repository.create_subscription_after_charge(
        user,
        offer,
        "searchable_sub",
        "https://panel.example/sub/searchable_sub",
        "2026-07-20T00:00:00+00:00",
    )
    results = await repository.search_users("searchable_sub")
    assert any(item.id == user.id for item in results)


def test_subscription_status_emoji_maps_known_states():
    from bot.admin_users import subscription_status_emoji

    assert subscription_status_emoji("active") == "🟢"
    assert subscription_status_emoji("expired") == "🔴"
    assert subscription_status_emoji("disabled") == "⚫"
    assert subscription_status_emoji("limited") == "🟠"


def test_format_traffic_usage_block_with_marzban_stats():
    from bot.admin_users import format_traffic_usage_block
    from bot.marzban import MarzbanUserStats

    usage = MarzbanUserStats(
        username="sub_abc",
        status="active",
        used_traffic=2 * 1024**3,
        data_limit=10 * 1024**3,
        expire=None,
    )
    lines = format_traffic_usage_block(usage=usage, fallback_total_gb=10)
    assert any("باقی‌مانده" in line for line in lines)
    assert any("2.00" in line for line in lines)


def test_admin_user_subscriptions_keyboard_callback_lengths():
    from bot.admin_users import admin_user_subscriptions_keyboard
    from bot.db import Subscription

    subscriptions = [
        Subscription(
            id=index,
            user_id=1,
            plan_id=None,
            marzban_username=f"user_sub_{index}",
            subscription_url=f"https://panel.example/sub/{index}",
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
        for index in range(1, 4)
    ]
    keyboard = admin_user_subscriptions_keyboard(user_id=1, subscriptions=subscriptions, page=1, total_subscriptions=3)
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data:
                assert len(button.callback_data.encode("utf-8")) <= 64


def test_admin_users_list_keyboard_has_inline_search():
    from bot.db import User

    users = [
        User(
            id=1,
            telegram_id=10_001,
            role="buyer",
            wallet_balance=1000,
            referral_code="code1",
            referred_by=None,
            first_name="User",
            username="user1",
        )
    ]
    keyboard = admin_users_list_keyboard(users=users, page=1, total_users=1)
    search_button = keyboard.inline_keyboard[2][0]

    assert search_button.text == "🔎 جستجو"
    assert search_button.switch_inline_query_current_chat == "users:"


def test_admin_users_list_keyboard_callback_lengths():
    from bot.db import User

    users = [
        User(
            id=index,
            telegram_id=10_000 + index,
            role="buyer",
            wallet_balance=1000,
            referral_code=f"code{index}",
            referred_by=None,
            first_name="User",
            username=f"user{index}",
        )
        for index in range(1, 4)
    ]
    keyboard = admin_users_list_keyboard(users=users, page=1, total_users=3)
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data:
                assert len(button.callback_data.encode("utf-8")) <= 64
