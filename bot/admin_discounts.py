from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import constants as c
from bot.db import DiscountCode


def discount_uses_label(code: DiscountCode) -> str:
    if code.max_uses > 0:
        return f"{code.used_count}/{code.max_uses}"
    return f"{code.used_count}/∞"


def discount_expiry_label(code: DiscountCode) -> str:
    if code.expires_at:
        return f"تا {code.expires_at[:10]}"
    return "بدون محدودیت زمانی"


def discount_status_label(code: DiscountCode) -> str:
    return "فعال" if code.active else "غیرفعال"


def discount_list_line(code: DiscountCode) -> str:
    status = "✅" if code.active else "⛔"
    return f"{status} {code.code.upper()} — {code.discount_percent}٪ — {discount_uses_label(code)} — {discount_expiry_label(code)}"


def discount_detail_text(code: DiscountCode) -> str:
    return "\n".join(
        [
            "جزئیات کد تخفیف",
            "",
            f"کد: {code.code.upper()}",
            f"درصد: {code.discount_percent}٪",
            f"استفاده: {discount_uses_label(code)}",
            f"اعتبار: {discount_expiry_label(code)}",
            f"وضعیت: {discount_status_label(code)}",
        ]
    )


def admin_discounts_list_keyboard(codes: list[DiscountCode]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for code in codes[:20]:
        label = f"{code.code.upper()} · {code.discount_percent}٪"
        if not code.active:
            label = f"⛔ {label}"
        if len(label) > 64:
            label = f"{label[:61]}…"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"discount:view:{code.id}")])
    rows.append([InlineKeyboardButton(text="➕ کد جدید", callback_data="admin:discounts:add")])
    rows.append([InlineKeyboardButton(text="بازگشت", callback_data="admin:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_discount_detail_keyboard(code_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="ویرایش درصد", callback_data=f"discount:edit:{code_id}:percent"),
                InlineKeyboardButton(text="ویرایش سقف استفاده", callback_data=f"discount:edit:{code_id}:max_uses"),
            ],
            [
                InlineKeyboardButton(text="ویرایش مدت اعتبار", callback_data=f"discount:edit:{code_id}:valid_days"),
            ],
            [
                InlineKeyboardButton(text="🗑 حذف کد", callback_data=f"discount:del:{code_id}"),
            ],
            [
                InlineKeyboardButton(text="🔙 لیست کدها", callback_data="admin:discounts"),
            ],
        ]
    )


def admin_discount_delete_confirm_keyboard(code_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="بله، حذف شود", callback_data=f"discount:del:{code_id}:yes"),
                InlineKeyboardButton(text="انصراف", callback_data=f"discount:view:{code_id}"),
            ],
        ]
    )


def admin_discount_edit_max_uses_keyboard(code_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="♾️ نامحدود", callback_data=f"discount:edit:{code_id}:max_uses:0")],
            [InlineKeyboardButton(text=c.BACK, callback_data=f"discount:view:{code_id}")],
        ]
    )


def admin_discount_edit_valid_days_keyboard(code_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="♾️ نامحدود", callback_data=f"discount:edit:{code_id}:valid_days:0")],
            [InlineKeyboardButton(text=c.BACK, callback_data=f"discount:view:{code_id}")],
        ]
    )
