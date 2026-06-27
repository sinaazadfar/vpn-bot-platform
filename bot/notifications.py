from __future__ import annotations

from aiogram import Bot

from bot.db import User
from bot.formatting import with_footer
from bot.keyboards import back_to_main_keyboard, wallet_after_approval_keyboard


def wallet_payment_approved_user_text(*, amount: int, balance: int) -> str:
    return "\n".join(
        [
            "💳 <b>تأیید پرداخت</b>",
            "",
            f"✅ پرداخت شما به مبلغ <b>{amount:,}</b> تومان تأیید شد.",
            f"مبلغ به کیف پول شما اضافه شد.",
            "",
            f"💰 موجودی فعلی: <b>{balance:,}</b> تومان",
        ]
    )


def wallet_payment_rejected_user_text(*, amount: int) -> str:
    return "\n".join(
        [
            "💳 <b>رد پرداخت</b>",
            "",
            f"پرداخت شما به مبلغ <b>{amount:,}</b> تومان رد شد.",
            "",
            "در صورت نیاز با پشتیبانی تماس بگیرید یا رسید صحیح ارسال کنید.",
        ]
    )


async def notify_wallet_payment_review(bot: Bot, user: User, *, amount: int, approved: bool, balance: int = 0) -> bool:
    if approved:
        text = with_footer(wallet_payment_approved_user_text(amount=amount, balance=balance))
        keyboard = wallet_after_approval_keyboard()
    else:
        text = with_footer(wallet_payment_rejected_user_text(amount=amount))
        keyboard = back_to_main_keyboard()
    try:
        await bot.send_message(user.telegram_id, text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        return False
    return True


WALLET_REASON_LABELS = {
    "admin_adjust": "تغییر توسط ادمین",
    "payment_approved": "شارژ کیف پول",
    "subscription_purchase": "خرید اشتراک",
    "subscription_extend": "تمدید اشتراک",
    "subscription_renew": "تمدید اشتراک",
    "subscription_volume": "افزایش حجم",
    "referral_commission": "پورسانت دعوت",
}


def wallet_reason_label(reason: str) -> str:
    return WALLET_REASON_LABELS.get(reason, reason)
