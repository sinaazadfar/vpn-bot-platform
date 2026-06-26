from __future__ import annotations

from aiogram import Router
from aiogram.types import InlineQuery

from bot.admin_inline import INLINE_RESULTS_LIMIT, build_empty_inline_article, build_user_inline_articles
from bot.context import AppContext
from bot.db import Repository

router = Router()


@router.inline_query()
async def admin_inline_user_search(query: InlineQuery, ctx: AppContext) -> None:
    if query.from_user is None or query.from_user.id not in ctx.settings.admin_ids:
        await query.answer(
            [],
            cache_time=0,
            is_personal=True,
            switch_pm_text="جستجوی کاربر فقط برای ادمین در دسترس است.",
        )
        return

    search_query = (query.query or "").strip()
    async with ctx.database.session() as db:
        repository = Repository(db)
        if search_query:
            users = await repository.search_users(search_query, limit=INLINE_RESULTS_LIMIT)
        else:
            users = await repository.list_users_page(page=1, per_page=INLINE_RESULTS_LIMIT)
        subscription_counts = {
            user.id: await repository.count_user_subscriptions(user.id)
            for user in users
        }

    articles = build_user_inline_articles(users, subscription_counts=subscription_counts)
    if not articles and search_query:
        articles = [build_empty_inline_article(search_query)]

    await query.answer(articles, cache_time=10, is_personal=True)
