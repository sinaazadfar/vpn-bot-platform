from __future__ import annotations

import datetime as dt

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine, session_scope
from vpn_bot_platform.common.models import MarzbanPanel, ResellerPanelAssignment
from vpn_bot_platform.common.repositories import consume_rate_limit_token
from vpn_bot_platform.common.rate_limit import (
    AdminRateLimitConfig,
    AdminRateLimitMiddleware,
    admin_bucket_key,
    admin_callback_bucket_key,
)
from vpn_bot_platform.integrations.payments import CardToCardGatewayAdapter
from vpn_bot_platform.master_bot.filters import SuperUserFilter
from vpn_bot_platform.seller_bot.panel_routing import PanelRouter


class _Settings:
    super_user_telegram_id = 252486544


class _User:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _Event:
    def __init__(self, user_id: int | None) -> None:
        self.from_user = _User(user_id) if user_id is not None else None


def _message(user_id: int, text: str = "/admin") -> Message:
    return Message(
        message_id=1,
        date=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        chat=Chat(id=user_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        text=text,
    )


def _callback(user_id: int, data: str) -> CallbackQuery:
    return CallbackQuery(
        id="callback-id",
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        chat_instance="chat-instance",
        data=data,
    )


async def _async_bool(value: bool) -> bool:
    return value


@pytest.mark.asyncio
async def test_super_user_filter_allows_only_owner_events() -> None:
    user_filter = SuperUserFilter(_Settings())  # type: ignore[arg-type]

    assert await user_filter(_Event(252486544)) is True  # type: ignore[arg-type]
    assert await user_filter(_Event(123)) is False  # type: ignore[arg-type]
    assert await user_filter(_Event(None)) is False  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rate_limit_bucket_rejects_after_limit() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    try:
        async with session_scope() as session:
            allowed, remaining = await consume_rate_limit_token(
                session,
                scope="test",
                identity="42",
                bucket_key="/start",
                limit=2,
                window_seconds=60,
                now=now,
            )
            assert allowed is True
            assert remaining == 1

            allowed, remaining = await consume_rate_limit_token(
                session,
                scope="test",
                identity="42",
                bucket_key="/start",
                limit=2,
                window_seconds=60,
                now=now + dt.timedelta(seconds=1),
            )
            assert allowed is True
            assert remaining == 0

            allowed, remaining = await consume_rate_limit_token(
                session,
                scope="test",
                identity="42",
                bucket_key="/start",
                limit=2,
                window_seconds=60,
                now=now + dt.timedelta(seconds=2),
            )
            assert allowed is False
            assert remaining == 0
    finally:
        await dispose_engine()


@pytest.mark.asyncio
async def test_rate_limit_buckets_are_isolated_by_scope_identity_and_action() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    try:
        async with session_scope() as session:
            assert (
                await consume_rate_limit_token(
                    session,
                    scope="seller_bot_admin:seller-1",
                    identity="42",
                    bucket_key="approvepay",
                    limit=1,
                    window_seconds=60,
                    now=now,
                )
            )[0] is True
            assert (
                await consume_rate_limit_token(
                    session,
                    scope="seller_bot_admin:seller-1",
                    identity="42",
                    bucket_key="approvepay",
                    limit=1,
                    window_seconds=60,
                    now=now,
                )
            )[0] is False
            assert (
                await consume_rate_limit_token(
                    session,
                    scope="seller_bot_admin:seller-2",
                    identity="42",
                    bucket_key="approvepay",
                    limit=1,
                    window_seconds=60,
                    now=now,
                )
            )[0] is True
            assert (
                await consume_rate_limit_token(
                    session,
                    scope="seller_bot_admin:seller-1",
                    identity="43",
                    bucket_key="approvepay",
                    limit=1,
                    window_seconds=60,
                    now=now,
                )
            )[0] is True
            assert (
                await consume_rate_limit_token(
                    session,
                    scope="seller_bot_admin:seller-1",
                    identity="42",
                    bucket_key="rejectpay",
                    limit=1,
                    window_seconds=60,
                    now=now,
                )
            )[0] is True
    finally:
        await dispose_engine()


def test_admin_rate_limit_bucket_keys_for_messages_and_callbacks() -> None:
    assert admin_bucket_key(_message(42, "/admin")) == "admin"
    assert admin_bucket_key(_message(42, "reply body")) == "message"
    assert admin_callback_bucket_key("admin:payments:0") == "admin:payments"
    assert admin_callback_bucket_key("admin:plans:0") == "admin:plans"
    assert admin_callback_bucket_key("approvepay:payment-1") == "approvepay"
    assert admin_callback_bucket_key("rejectpay:payment-1") == "rejectpay"
    assert admin_callback_bucket_key("provision:order-1") == "provision"
    assert admin_callback_bucket_key("approvetx:tx-1") == "approvetx"
    assert admin_callback_bucket_key("rejecttx:tx-1") == "rejecttx"


@pytest.mark.asyncio
async def test_admin_rate_limit_middleware_skips_non_admin_users() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    calls = 0

    async def handler(event, data):
        nonlocal calls
        calls += 1
        return "ok"

    middleware = AdminRateLimitMiddleware(
        AdminRateLimitConfig(scope="seller_bot_admin:seller-1", limit=1),
        is_admin=lambda telegram_id: _async_bool(False),
    )
    try:
        assert await middleware(handler, _message(42, "/admin"), {}) == "ok"
        assert await middleware(handler, _message(42, "/admin"), {}) == "ok"
    finally:
        await dispose_engine()

    assert calls == 2


@pytest.mark.asyncio
async def test_admin_rate_limit_middleware_throttles_admin_messages_separately() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    calls = 0

    async def handler(event, data):
        nonlocal calls
        calls += 1
        return "ok"

    async def answer(self, *args, **kwargs):
        return None

    original_answer = Message.answer
    Message.answer = answer
    middleware = AdminRateLimitMiddleware(
        AdminRateLimitConfig(scope="seller_bot_admin:seller-1", limit=1),
        is_admin=lambda telegram_id: _async_bool(True),
    )
    try:
        assert await middleware(handler, _message(42, "/admin"), {}) == "ok"
        assert await middleware(handler, _message(42, "/admin"), {}) is None
        assert calls == 1
        assert await middleware(handler, _message(43, "/admin"), {}) == "ok"
        assert calls == 2
    finally:
        Message.answer = original_answer
        await dispose_engine()


@pytest.mark.asyncio
async def test_admin_rate_limit_middleware_uses_sensitive_limit_for_callbacks() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    calls = 0

    async def handler(event, data):
        nonlocal calls
        calls += 1
        return "ok"

    async def answer(self, *args, **kwargs):
        return None

    original_answer = CallbackQuery.answer
    CallbackQuery.answer = answer
    middleware = AdminRateLimitMiddleware(
        AdminRateLimitConfig(
            scope="seller_bot_admin:seller-1",
            limit=10,
            sensitive_limit=1,
        ),
        is_admin=lambda telegram_id: _async_bool(True),
    )
    try:
        assert await middleware(handler, _callback(42, "approvepay:payment-1"), {}) == "ok"
        assert await middleware(handler, _callback(42, "approvepay:payment-1"), {}) is None
        assert calls == 1
    finally:
        CallbackQuery.answer = original_answer
        await dispose_engine()


def test_card_to_card_gateway_returns_manual_intent() -> None:
    adapter = CardToCardGatewayAdapter(instructions="Pay to card 1234")

    intent = adapter.create_payment_intent(
        amount=100_000,
        description="order:1",
        buyer_telegram_id=252486544,
    )

    assert intent.provider == "card_to_card"
    assert intent.instructions == "Pay to card 1234"
    assert intent.external_reference == "manual:252486544:100000"


@pytest.mark.asyncio
async def test_panel_router_uses_priority_then_weight() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    try:
        async with session_scope() as session:
            panel_low = MarzbanPanel(name="low", base_url="https://low.example")
            panel_high = MarzbanPanel(name="high", base_url="https://high.example")
            session.add_all([panel_low, panel_high])
            await session.flush()
            reseller_id = "reseller-1"
            session.add_all(
                [
                    ResellerPanelAssignment(
                        reseller_id=reseller_id,
                        panel_id=panel_low.id,
                        priority=200,
                        weight=100,
                    ),
                    ResellerPanelAssignment(
                        reseller_id=reseller_id,
                        panel_id=panel_high.id,
                        priority=100,
                        weight=1,
                    ),
                ]
            )
            await session.flush()

            routed = await PanelRouter().choose_panel(session, reseller_id=reseller_id)
    finally:
        await dispose_engine()

    assert routed is not None
    assert routed.panel.id == panel_high.id
