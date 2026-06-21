import pytest
import pytest_asyncio

from bot.db import Database, Repository


@pytest_asyncio.fixture
async def repository(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    await database.init()
    async with database.session() as db:
        yield Repository(db)


@pytest.mark.asyncio
async def test_payment_approval_adds_wallet_once(repository):
    user = await repository.ensure_user(1001, set())
    payment = await repository.create_payment(user.id, 250_000, "photo-id")

    reviewed = await repository.review_payment(payment.id, user.id, approved=True)
    second_review = await repository.review_payment(payment.id, user.id, approved=True)
    updated = await repository.get_user_by_telegram_id(1001)

    assert reviewed.status == "approved"
    assert second_review is None
    assert updated.wallet_balance == 250_000


@pytest.mark.asyncio
async def test_payment_decline_does_not_change_wallet(repository):
    user = await repository.ensure_user(1002, set())
    payment = await repository.create_payment(user.id, 100_000, "photo-id")

    reviewed = await repository.review_payment(payment.id, user.id, approved=False)
    updated = await repository.get_user_by_telegram_id(1002)

    assert reviewed.status == "declined"
    assert updated.wallet_balance == 0


@pytest.mark.asyncio
async def test_purchase_deducts_after_subscription_record(repository):
    user = await repository.ensure_user(1003, set())
    await repository.adjust_wallet(user.id, 500_000, "seed")
    await repository.db.commit()
    user = await repository.get_user_by_telegram_id(1003)
    settings = await repository.update_pricing_settings(per_gb_price=10_000, three_month_extra_price=50_000)
    offer = repository.build_offer(settings, 20, 30, "preset", 10)

    subscription = await repository.create_subscription_after_charge(
        user,
        offer,
        "tg_1003",
        "https://panel.example.com/sub/tg_1003",
        "2026-07-20T00:00:00+00:00",
    )
    updated = await repository.get_user_by_telegram_id(1003)

    assert subscription.status == "active"
    assert subscription.traffic_gb == 20
    assert subscription.duration_days == 30
    assert subscription.discount_percent == 10
    assert subscription.final_price == 180_000
    assert updated.wallet_balance == 320_000


@pytest.mark.asyncio
async def test_insufficient_balance_blocks_purchase(repository):
    user = await repository.ensure_user(1004, set())
    settings = await repository.update_pricing_settings(per_gb_price=10_000)
    offer = repository.build_offer(settings, 50, 30, "manual")

    with pytest.raises(ValueError, match="insufficient_balance"):
        await repository.create_subscription_after_charge(
            user,
            offer,
            "tg_1004",
            "https://panel.example.com/sub/tg_1004",
            "2026-07-20T00:00:00+00:00",
        )

    updated = await repository.get_user_by_telegram_id(1004)
    subscriptions = await repository.list_user_subscriptions(user.id)
    assert updated.wallet_balance == 0
    assert subscriptions == []


@pytest.mark.asyncio
async def test_pricing_defaults_create_presets(repository):
    settings = await repository.get_pricing_settings()
    presets = await repository.list_traffic_presets()

    assert settings.one_month_enabled is True
    assert settings.three_month_enabled is True
    assert [preset.gb for preset in presets] == [5, 10, 15, 20, 50, 75, 100]


@pytest.mark.asyncio
async def test_init_deletes_old_manual_plans(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    await database.init()
    async with database.session() as db:
        await db.execute(
            """
            INSERT INTO plans (title, price, duration_days, traffic_gb, marzban_settings, active, created_at, updated_at)
            VALUES ('legacy', 1000, 30, 10, '{}', 1, 'now', 'now')
            """
        )
        await db.commit()

    await database.init()

    async with database.session() as db:
        async with db.execute("SELECT COUNT(*) FROM plans") as cur:
            count = (await cur.fetchone())[0]
    assert count == 0


@pytest.mark.asyncio
async def test_preset_price_uses_full_price_discount_for_three_month(repository):
    settings = await repository.update_pricing_settings(per_gb_price=10_000, three_month_extra_price=100_000)
    offer = repository.build_offer(settings, 50, 90, "preset", 20)

    assert offer.base_price == 500_000
    assert offer.duration_extra == 100_000
    assert offer.discount_percent == 20
    assert offer.final_price == 480_000


@pytest.mark.asyncio
async def test_manual_gb_has_no_discount(repository):
    settings = await repository.update_pricing_settings(per_gb_price=10_000, three_month_extra_price=100_000)
    offer = repository.build_offer(settings, 50, 90, "manual", 99)

    assert offer.discount_percent == 0
    assert offer.final_price == 600_000


@pytest.mark.asyncio
async def test_manual_gb_bounds(repository):
    settings = await repository.update_pricing_settings(per_gb_price=10_000)

    with pytest.raises(ValueError, match="invalid_traffic"):
        repository.build_offer(settings, 0, 30, "manual")
    with pytest.raises(ValueError, match="invalid_traffic"):
        repository.build_offer(settings, 201, 30, "manual")


@pytest.mark.asyncio
async def test_disabled_duration_cannot_build_offer(repository):
    settings = await repository.update_pricing_settings(per_gb_price=10_000, three_month_enabled=False)

    with pytest.raises(ValueError, match="duration_disabled"):
        repository.build_offer(settings, 10, 90, "preset", 0)


@pytest.mark.asyncio
async def test_subscription_pagination_returns_latest_ten(repository):
    user = await repository.ensure_user(2001, set())
    await repository.adjust_wallet(user.id, 5_000_000, "seed")
    await repository.db.commit()
    user = await repository.get_user_by_telegram_id(2001)
    settings = await repository.update_pricing_settings(per_gb_price=1_000)
    offer = repository.build_offer(settings, 1, 30, "manual")
    for index in range(11):
        await repository.create_subscription_after_charge(
            user,
            offer,
            f"user_{index}",
            f"https://panel.example/sub/user_{index}",
            "2026-07-20T00:00:00+00:00",
        )
        user = await repository.get_user_by_telegram_id(2001)

    assert await repository.count_user_subscriptions(user.id) == 11
    page_1 = await repository.list_user_subscriptions_page(user.id, 1, 10)
    page_2 = await repository.list_user_subscriptions_page(user.id, 2, 10)

    assert len(page_1) == 10
    assert len(page_2) == 1
    assert page_1[0].marzban_username == "user_10"
    assert page_2[0].marzban_username == "user_0"


@pytest.mark.asyncio
async def test_extend_subscription_updates_same_row_and_charges_wallet(repository):
    user = await repository.ensure_user(2002, set())
    await repository.adjust_wallet(user.id, 1_000_000, "seed")
    await repository.db.commit()
    user = await repository.get_user_by_telegram_id(2002)
    settings = await repository.update_pricing_settings(per_gb_price=1_000)
    offer = repository.build_offer(settings, 10, 30, "manual")
    subscription = await repository.create_subscription_after_charge(
        user,
        offer,
        "user_ext",
        "https://panel.example/sub/user_ext",
        "2026-07-20T00:00:00+00:00",
    )
    user = await repository.get_user_by_telegram_id(2002)
    extension_offer = repository.build_offer(settings, 5, 90, "manual")

    updated = await repository.extend_subscription_after_charge(
        user,
        subscription,
        extension_offer,
        "2026-10-18T00:00:00+00:00",
    )
    charged_user = await repository.get_user_by_telegram_id(2002)

    assert updated.id == subscription.id
    assert updated.traffic_gb == 15
    assert updated.duration_days == 120
    assert updated.final_price == 15_000
    assert charged_user.wallet_balance == 985_000


@pytest.mark.asyncio
async def test_earning_settings_default_disabled_and_zero_percent(repository):
    assert await repository.get_earning_enabled() is False
    assert await repository.get_earning_percent() == 0


@pytest.mark.asyncio
async def test_earning_settings_persist_and_validate(repository):
    await repository.set_earning_enabled(True)
    await repository.set_earning_percent(15)

    assert await repository.get_earning_enabled() is True
    assert await repository.get_earning_percent() == 15
    with pytest.raises(ValueError, match="invalid_earning_percent"):
        await repository.set_earning_percent(101)


@pytest.mark.asyncio
async def test_new_purchase_credits_one_level_referrer_wallet(repository):
    referrer = await repository.ensure_user(3001, set())
    buyer = await repository.ensure_user(3002, set(), referred_by=referrer.id)
    await repository.adjust_wallet(buyer.id, 500_000, "seed")
    await repository.set_earning_enabled(True)
    await repository.set_earning_percent(10)
    await repository.db.commit()
    buyer = await repository.get_user_by_telegram_id(3002)
    settings = await repository.update_pricing_settings(per_gb_price=10_000)
    offer = repository.build_offer(settings, 20, 30, "manual")

    subscription = await repository.create_subscription_after_charge(
        buyer,
        offer,
        "buyer_sub",
        "https://panel.example/sub/buyer_sub",
        "2026-07-20T00:00:00+00:00",
    )
    updated_buyer = await repository.get_user_by_telegram_id(3002)
    updated_referrer = await repository.get_user_by_telegram_id(3001)
    rows = await repository._fetchall(
        "SELECT * FROM wallet_transactions WHERE reason = 'referral_commission' AND linked_subscription_id = ?",
        (subscription.id,),
    )

    assert updated_buyer.wallet_balance == 300_000
    assert updated_referrer.wallet_balance == 20_000
    assert await repository.get_referral_earnings_total(referrer.id) == 20_000
    assert len(rows) == 1
    assert rows[0]["user_id"] == referrer.id
    assert rows[0]["amount"] == 20_000


@pytest.mark.asyncio
async def test_disabled_earning_creates_no_commission(repository):
    referrer = await repository.ensure_user(3003, set())
    buyer = await repository.ensure_user(3004, set(), referred_by=referrer.id)
    await repository.adjust_wallet(buyer.id, 500_000, "seed")
    await repository.set_earning_percent(10)
    await repository.db.commit()
    buyer = await repository.get_user_by_telegram_id(3004)
    settings = await repository.update_pricing_settings(per_gb_price=10_000)
    offer = repository.build_offer(settings, 20, 30, "manual")

    await repository.create_subscription_after_charge(
        buyer,
        offer,
        "buyer_no_commission",
        "https://panel.example/sub/buyer_no_commission",
        "2026-07-20T00:00:00+00:00",
    )
    updated_referrer = await repository.get_user_by_telegram_id(3003)

    assert updated_referrer.wallet_balance == 0
    assert await repository.get_referral_earnings_total(referrer.id) == 0


@pytest.mark.asyncio
async def test_extension_does_not_credit_referrer(repository):
    referrer = await repository.ensure_user(3005, set())
    buyer = await repository.ensure_user(3006, set(), referred_by=referrer.id)
    await repository.adjust_wallet(buyer.id, 500_000, "seed")
    await repository.set_earning_enabled(True)
    await repository.set_earning_percent(10)
    await repository.db.commit()
    buyer = await repository.get_user_by_telegram_id(3006)
    settings = await repository.update_pricing_settings(per_gb_price=10_000)
    offer = repository.build_offer(settings, 10, 30, "manual")
    subscription = await repository.create_subscription_after_charge(
        buyer,
        offer,
        "buyer_ext",
        "https://panel.example/sub/buyer_ext",
        "2026-07-20T00:00:00+00:00",
    )
    referrer_after_purchase = await repository.get_user_by_telegram_id(3005)
    buyer = await repository.get_user_by_telegram_id(3006)
    extension_offer = repository.build_offer(settings, 5, 30, "manual")

    await repository.extend_subscription_after_charge(
        buyer,
        subscription,
        extension_offer,
        "2026-08-19T00:00:00+00:00",
    )
    referrer_after_extension = await repository.get_user_by_telegram_id(3005)

    assert referrer_after_purchase.wallet_balance == 10_000
    assert referrer_after_extension.wallet_balance == 10_000
