from __future__ import annotations

from bot.db import PurchaseOffer
from bot.formatting import with_footer


def discount_error_message(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        messages = {
            "discount_empty": "کد تخفیف را وارد کنید.",
            "discount_not_found": "کد تخفیف معتبر نیست.",
            "discount_expired": "مهلت استفاده از این کد تخفیف تمام شده است.",
            "discount_exhausted": "سقف استفاده از این کد تخفیف پر شده است.",
            "discount_already_used": "شما قبلاً از این کد تخفیف استفاده کرده‌اید.",
            "coupon_redeem_failed": "کد تخفیف قابل استفاده نیست.",
        }
        return messages.get(str(exc), "کد تخفیف معتبر نیست.")
    return "کد تخفیف معتبر نیست."


def purchase_confirm_text(offer: PurchaseOffer, *, coupon_percent: int = 0, coupon_code: str = "") -> str:
    lines = [
        "تایید خرید",
        f"حجم: {offer.traffic_gb} GB",
        f"مدت: {offer.duration_days} روز",
        f"قیمت حجم: {offer.base_price:,} تومان",
        f"هزینه مدت: {offer.duration_extra:,} تومان",
        f"تخفیف حجم: {offer.discount_percent}٪",
    ]
    if coupon_percent > 0:
        lines.append(f"کد تخفیف: {coupon_code.upper()} ({coupon_percent}٪)")
    lines.append(f"مبلغ نهایی: {offer.final_price:,} تومان")
    return with_footer("\n".join(lines))
