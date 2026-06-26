from __future__ import annotations

from dataclasses import dataclass

from bot.context import AppContext
from bot.db import Repository, Subscription, User
from bot.marzban import MarzbanError, MarzbanSubscription


@dataclass(frozen=True)
class TrialActivationResult:
    subscription: Subscription
    marzban_sub: MarzbanSubscription
    traffic_mb: int
    days: int


async def should_show_trial_button(repository: Repository, user_id: int) -> bool:
    if not await repository.get_trial_enabled():
        return False
    return not await repository.has_trial_grant(user_id)


async def activate_trial(repository: Repository, user: User, ctx: AppContext) -> TrialActivationResult:
    if not await repository.get_trial_enabled():
        raise ValueError("trial_disabled")
    if await repository.has_trial_grant(user.id):
        raise ValueError("trial_already_used")
    traffic_mb = await repository.get_trial_traffic_mb()
    days = await repository.get_trial_days()
    offer = repository.build_offer(await repository.get_pricing_settings(), 0, days, "trial", 100)
    await ctx.quota.ensure_available(repository, requested_gb=0)
    marzban_sub = await ctx.marzban.create_trial_subscription(
        f"trial_{user.telegram_id}",
        data_limit_mb=traffic_mb,
        duration_days=days,
    )
    await repository.grant_trial(user.id)
    subscription = await repository.create_subscription_after_charge(
        user,
        offer,
        marzban_sub.username,
        marzban_sub.subscription_url,
        marzban_sub.expires_at,
    )
    return TrialActivationResult(
        subscription=subscription,
        marzban_sub=marzban_sub,
        traffic_mb=traffic_mb,
        days=days,
    )


def trial_error_message(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        if str(exc) == "trial_disabled":
            return "تست رایگان فعال نیست."
        if str(exc) == "trial_already_used":
            return "قبلاً تست رایگان دریافت کرده‌اید."
    if isinstance(exc, MarzbanError):
        return str(exc)[:180]
    return str(exc)[:180]
