import pytest
import pytest_asyncio

from bot.db import Database, Repository, normalize_support_username
from bot.keyboards import main_menu


@pytest_asyncio.fixture
async def repository(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    await database.init()
    async with database.session() as db:
        yield Repository(db)


def test_normalize_support_username_accepts_common_forms():
    assert normalize_support_username("@Support_User") == "Support_User"
    assert normalize_support_username("Support_User") == "Support_User"
    assert normalize_support_username("https://t.me/Support_User") == "Support_User"
    assert normalize_support_username("t.me/Support_User/") == "Support_User"


def test_normalize_support_username_rejects_invalid_values():
    assert normalize_support_username("") == ""
    assert normalize_support_username("@bad-name") == ""
    assert normalize_support_username("@abc") == ""


@pytest.mark.asyncio
async def test_support_username_persists(repository):
    stored = await repository.set_support_username("@Support_User")

    assert stored == "Support_User"
    assert await repository.get_support_username() == "Support_User"


def test_main_menu_support_button_uses_url_when_configured():
    keyboard = main_menu(False, support_username="Support_User")
    support_button = keyboard.inline_keyboard[3][1]

    assert support_button.url == "https://t.me/Support_User"
    assert support_button.callback_data is None


def test_main_menu_support_button_falls_back_to_callback():
    keyboard = main_menu(False)
    support_button = keyboard.inline_keyboard[3][1]

    assert support_button.callback_data == "menu:support"
    assert support_button.url is None
