import pytest
import pytest_asyncio

from bot.admin_users import USERS_PER_PAGE, admin_users_list_keyboard, user_display_name, users_total_pages
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


def test_users_total_pages():
    assert users_total_pages(0) == 1
    assert users_total_pages(1) == 1
    assert users_total_pages(USERS_PER_PAGE) == 1
    assert users_total_pages(USERS_PER_PAGE + 1) == 2


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
