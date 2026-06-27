from __future__ import annotations

from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import constants as c
from bot.admin_users import user_button_title
from bot.db import PendingPaymentView

PAYMENTS_PER_PAGE = 8


def payments_total_pages(total: int) -> int:
    return max(1, ceil(total / PAYMENTS_PER_PAGE))


def payments_list_text(*, page: int, total: int) -> str:
    return "\n".join(
        [
            "پرداخت‌های در انتظار",
            "",
            f"تعداد: {total}",
            f"صفحه {page} از {payments_total_pages(total)}",
            "",
            "روی هر پرداخت بزنید برای جزئیات و تأیید/رد.",
        ]
    )


def payment_detail_text(item: PendingPaymentView) -> str:
    user = item.user
    payment = item.payment
    return "\n".join(
        [
            "جزئیات پرداخت",
            "",
            f"شناسه: #{payment.id}",
            f"کاربر: {user_button_title(user)}",
            f"مبلغ: {payment.amount:,} تومان",
            f"تاریخ: {payment.created_at[:19] if payment.created_at else '—'}",
        ]
    )


def pending_payments_list_keyboard(*, items: list[PendingPaymentView], page: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        label = f"#{item.payment.id} · {user_button_title(item.user)} · {item.payment.amount:,}"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=f"adm:pay:{item.payment.id}")])
    total_pages = payments_total_pages(total)
    if total_pages > 1:
        prev_page = max(page - 1, 1)
        next_page = min(page + 1, total_pages)
        rows.append(
            [
                InlineKeyboardButton(text="◀️", callback_data=f"adm:payments:page:{prev_page}"),
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
                InlineKeyboardButton(text="▶️", callback_data=f"adm:payments:page:{next_page}"),
            ]
        )
    rows.append([InlineKeyboardButton(text=c.BACK, callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_detail_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأیید", callback_data=f"pay_ok:{payment_id}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"pay_no:{payment_id}"),
            ],
            [InlineKeyboardButton(text="🖼 مشاهده رسید", callback_data=f"adm:pay:{payment_id}:receipt")],
            [
                InlineKeyboardButton(text="🔙 لیست پرداخت‌ها", callback_data="adm:payments:page:1"),
                InlineKeyboardButton(text=c.BACK, callback_data="admin:panel"),
            ],
        ]
    )
