from __future__ import annotations

import datetime as dt

import pytest

from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine, session_scope
from vpn_bot_platform.common.models import MarzbanPanel, ResellerPanelAssignment
from vpn_bot_platform.common.repositories import consume_rate_limit_token
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
