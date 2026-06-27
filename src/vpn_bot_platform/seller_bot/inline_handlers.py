from __future__ import annotations

from aiogram import Router
from aiogram.types import ChosenInlineResult, InlineQuery

from vpn_bot_platform.common.models import PlanPurpose
from vpn_bot_platform.seller_bot.handlers import (
    get_buyer_service,
    send_customer_detail_message,
    send_service_detail_message,
)
from vpn_bot_platform.seller_bot.inline_search import (
    INLINE_RESULTS_LIMIT,
    build_customer_inline_articles,
    build_empty_inline_article,
    build_service_inline_articles,
    parse_inline_query,
)
from vpn_bot_platform.seller_bot.services import SellerContextService

router = Router(name="seller_inline_search")


def _filter_services(services: list, query: str) -> list:
    if not query:
        return services[:INLINE_RESULTS_LIMIT]
    normalized = query.casefold()
    filtered = [
        service
        for service in services
        if normalized in service.id.casefold() or normalized in service.marzban_username.casefold()
    ]
    return filtered[:INLINE_RESULTS_LIMIT]


@router.inline_query()
async def inline_search(query: InlineQuery, seller_context: SellerContextService) -> None:
    if query.from_user is None:
        await query.answer([], cache_time=0, is_personal=True)
        return

    mode, search_query = parse_inline_query(query.query)
    if mode is None:
        await query.answer([], cache_time=0, is_personal=True)
        return

    if mode == "users":
        if not await seller_context.is_reseller_admin(telegram_id=query.from_user.id):
            await query.answer([], cache_time=0, is_personal=True)
            return
        try:
            if search_query:
                customers = await seller_context.search_customers(
                    admin_telegram_id=query.from_user.id,
                    query=search_query,
                )
            else:
                customers = await seller_context.list_customers(admin_telegram_id=query.from_user.id)
        except (PermissionError, ValueError):
            await query.answer([], cache_time=0, is_personal=True)
            return
        customers = customers[:INLINE_RESULTS_LIMIT]
        articles = build_customer_inline_articles(customers)
        if not articles and search_query:
            articles = [build_empty_inline_article(search_query, entity_label="کاربری")]
        await query.answer(articles, cache_time=10, is_personal=True)
        return

    services = await seller_context.list_buyer_services(buyer_telegram_id=query.from_user.id)
    services = _filter_services(services, search_query)
    articles = build_service_inline_articles(services)
    if not articles and search_query:
        articles = [build_empty_inline_article(search_query, entity_label="سرویسی")]
    await query.answer(articles, cache_time=10, is_personal=True)


@router.chosen_inline_result()
async def inline_result_chosen(result: ChosenInlineResult, seller_context: SellerContextService) -> None:
    if result.from_user is None or not result.result_id:
        return

    chat_id = result.from_user.id
    if result.result_id.startswith("user:"):
        if not await seller_context.is_reseller_admin(telegram_id=result.from_user.id):
            return
        buyer_id = result.result_id.split(":", 1)[1]
        if not buyer_id:
            return
        await send_customer_detail_message(
            result.bot,
            chat_id,
            seller_context,
            admin_telegram_id=result.from_user.id,
            buyer_id=buyer_id,
        )
        return

    if not result.result_id.startswith("service:"):
        return
    service_id = result.result_id.split(":", 1)[1]
    if not service_id:
        return
    service = await get_buyer_service(
        seller_context,
        buyer_telegram_id=result.from_user.id,
        service_id=service_id,
    )
    if service is None:
        return
    extra_plans = await seller_context.list_plans(purpose=PlanPurpose.EXTRA_VOLUME)
    await send_service_detail_message(
        result.bot,
        chat_id,
        service,
        show_extra_volume=bool(extra_plans),
    )
