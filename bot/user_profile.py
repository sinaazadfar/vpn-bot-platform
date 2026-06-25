from __future__ import annotations

import asyncio

from aiogram import Bot

from bot.admin_users import user_full_name
from bot.db import Repository, User


def user_needs_profile_sync(user: User) -> bool:
    return not user_full_name(user)


async def refresh_user_profile_from_telegram(bot: Bot, repository: Repository, user: User) -> User:
    if not user_needs_profile_sync(user):
        return user
    try:
        chat = await bot.get_chat(user.telegram_id)
    except Exception:
        return user
    updated = await repository.sync_telegram_profile(
        user.telegram_id,
        first_name=chat.first_name,
        last_name=chat.last_name,
        username=chat.username,
    )
    return updated or user


async def refresh_users_profiles_from_telegram(bot: Bot, repository: Repository, users: list[User]) -> list[User]:
    if not users:
        return users
    return list(await asyncio.gather(*(refresh_user_profile_from_telegram(bot, repository, user) for user in users)))
