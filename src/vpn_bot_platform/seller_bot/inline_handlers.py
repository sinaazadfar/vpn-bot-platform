from __future__ import annotations

from aiogram import Router
from aiogram.types import InlineQuery

from vpn_bot_platform.common.models import PlanPurpose
from vpn_bot_platform.seller_bot.handlers import (
    customer_detail_kb,
    customer_detail_text,
    render_text,
    service_detail_inline_text,
    service_detail_kb,
)
from vpn_bot_platform.seller_bot.inline_search import (
    INLINE_RESULTS_LIMIT,
    build_customer_inline_article,
    build_empty_inline_article,
    build_service_inline_article,
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
        articles = []
        for customer in customers[:INLINE_RESULTS_LIMIT]:
            try:
                detail = await seller_context.get_customer_detail(
                    admin_telegram_id=query.from_user.id,
                    buyer_id=customer.buyer.id,
                )
            except (PermissionError, ValueError):
                continue
            articles.append(
                build_customer_inline_article(
                    customer,
                    message_text=render_text(customer_detail_text(detail)),
                    reply_markup=customer_detail_kb(customer.buyer.id),
                )
            )
        if not articles and search_query:
            articles = [build_empty_inline_article(search_query, entity_label="کاربری")]
        await query.answer(articles, cache_time=10, is_personal=True)
        return

    services = await seller_context.list_buyer_services(buyer_telegram_id=query.from_user.id)
    services = _filter_services(services, search_query)
    extra_plans = await seller_context.list_plans(purpose=PlanPurpose.EXTRA_VOLUME)
    show_extra_volume = bool(extra_plans)
    articles = [
        build_service_inline_article(
            service,
            message_text=render_text(service_detail_inline_text(service)),
            reply_markup=service_detail_kb(service.id, show_extra_volume=show_extra_volume),
        )
        for service in services
    ]
    if not articles and search_query:
        articles = [build_empty_inline_article(search_query, entity_label="سرویسی")]
    await query.answer(articles, cache_time=10, is_personal=True)
