import re

import pytest
import pytest_asyncio

from bot.db import Database, Repository, generate_referral_code, normalize_referral_code


@pytest_asyncio.fixture
async def repository(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    await database.init()
    async with database.session() as db:
        yield Repository(db)


def test_generate_referral_code_is_lowercase_alphanumeric():
    code = generate_referral_code()

    assert len(code) == 8
    assert re.fullmatch(r"[a-z0-9]+", code)
    assert "-" not in code
    assert "_" not in code


def test_normalize_referral_code_handles_upper_and_invalid_chars():
    assert normalize_referral_code(" AB-C_123 ") == "abc123"


@pytest.mark.asyncio
async def test_ensure_user_generates_valid_referral_code(repository):
    user = await repository.ensure_user(3001, set())

    assert re.fullmatch(r"[a-z0-9]{8}", user.referral_code)


@pytest.mark.asyncio
async def test_referral_lookup_is_case_insensitive(repository):
    user = await repository.ensure_user(3002, set())

    found = await repository.get_user_by_referral_code(user.referral_code.upper())

    assert found.id == user.id


@pytest.mark.asyncio
async def test_referred_by_set_on_new_user(repository):
    referrer = await repository.ensure_user(3003, set())
    found = await repository.get_user_by_referral_code(referrer.referral_code.upper())
    referred = await repository.ensure_user(3004, set(), referred_by=found.id)

    assert referred.referred_by == referrer.id


@pytest.mark.asyncio
async def test_set_referred_by_if_empty_sets_once_and_does_not_overwrite(repository):
    first_referrer = await repository.ensure_user(5001, set())
    second_referrer = await repository.ensure_user(5002, set())
    user = await repository.ensure_user(5003, set())

    first_update = await repository.set_referred_by_if_empty(user.id, first_referrer.id)
    second_update = await repository.set_referred_by_if_empty(user.id, second_referrer.id)
    updated = await repository.get_user_by_telegram_id(5003)

    assert first_update is True
    assert second_update is False
    assert updated.referred_by == first_referrer.id


@pytest.mark.asyncio
async def test_set_referred_by_if_empty_ignores_self_referral(repository):
    user = await repository.ensure_user(5004, set())

    updated = await repository.set_referred_by_if_empty(user.id, user.id)
    fresh = await repository.get_user_by_telegram_id(5004)

    assert updated is False
    assert fresh.referred_by is None


@pytest.mark.asyncio
async def test_referral_migration_normalizes_existing_codes(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    await database.init()
    async with database.session() as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, role, wallet_balance, referral_code, created_at, updated_at)
            VALUES (4001, 'buyer', 0, 'AB-CD_12', 'now', 'now')
            """
        )
        await db.commit()

    await database.init()

    async with database.session() as db:
        row = await Repository(db)._fetchone("SELECT referral_code FROM users WHERE telegram_id = 4001")
    assert row["referral_code"] == "abcd12"
