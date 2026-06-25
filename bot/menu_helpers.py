from __future__ import annotations

from bot.context import AppContext
from bot.db import Repository, User
from bot.keyboards import main_menu


async def main_menu_for_user(repository: Repository, user: User, ctx: AppContext):
    support_username = await repository.get_support_username()
    earning_enabled = await repository.get_earning_enabled()
    trial_enabled = await repository.get_trial_enabled()
    return main_menu(
        user.role == "admin",
        ctx.settings.web_app_url,
        support_username,
        earning_enabled,
        trial_enabled,
    )
