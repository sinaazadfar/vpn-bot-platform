from __future__ import annotations

from aiogram import Router
from aiogram.types import ChosenInlineResult, InlineQuery

from bot.admin_inline import (
    INLINE_RESULTS_LIMIT,
    build_empty_inline_article,
    build_subscription_inline_articles,
    build_user_inline_articles,
    parse_inline_query,
)
from bot.admin_users import admin_user_detail_keyboard, user_detail_text
from bot.context import AppContext
from bot.db import Repository
from bot.formatting import with_footer
from bot.user_profile import refresh_user_profile_from_telegram

router = Router()


async def send_user_detail_message(bot, chat_id: int, ctx: AppContext, user_id: int) -> bool:
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.get_user(user_id)
        if user is None:
            return False
        user = await refresh_user_profile_from_telegram(bot, repository, user)
        subscription_count = await repository.count_user_subscriptions(user.id)
    await bot.send_message(
        chat_id,
        with_footer(user_detail_text(user=user, subscription_count=subscription_count)),
        reply_markup=admin_user_detail_keyboard(user=user),
    )
    return True


@router.inline_query()
async def inline_search(query: InlineQuery, ctx: AppContext) -> None:
    if query.from_user is None:
        await query.answer([], cache_time=0, is_personal=True)
        return

    mode, search_query = parse_inline_query(query.query)
    if mode is None:
        await query.answer([], cache_time=0, is_personal=True)
        return

    if mode == "users":
        if query.from_user.id not in ctx.settings.admin_ids:
            await query.answer([], cache_time=0, is_personal=True)
            return
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
            articles = [build_empty_inline_article(search_query, entity_label="کاربری")]
        await query.answer(articles, cache_time=10, is_personal=True)
        return

    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(query.from_user, ctx.settings.admin_ids)
        subscriptions = await repository.search_user_subscriptions(user.id, search_query, limit=INLINE_RESULTS_LIMIT)
    articles = build_subscription_inline_articles(subscriptions)
    if not articles and search_query:
        articles = [build_empty_inline_article(search_query, entity_label="اشتراکی")]
    await query.answer(articles, cache_time=10, is_personal=True)


@router.chosen_inline_result()
async def inline_result_chosen(result: ChosenInlineResult, ctx: AppContext) -> None:
    if result.from_user is None or not result.result_id:
        return

    chat_id = result.from_user.id
    if result.result_id.startswith("user:"):
        if result.from_user.id not in ctx.settings.admin_ids:
            return
        try:
            user_id = int(result.result_id.split(":", 1)[1])
        except ValueError:
            return
        await send_user_detail_message(result.bot, chat_id, ctx, user_id)
        return

    if not result.result_id.startswith("sub:"):
        return
    try:
        subscription_id = int(result.result_id.split(":", 1)[1])
    except ValueError:
        return
    async with ctx.database.session() as db:
        repository = Repository(db)
        user = await repository.ensure_user_from_telegram(result.from_user, ctx.settings.admin_ids)
        subscription = await repository.get_user_subscription(user.id, subscription_id)
    if subscription is None:
        return
    from bot.handlers.buyer import send_subscription_detail_message

    await send_subscription_detail_message(result.bot, chat_id, subscription)
