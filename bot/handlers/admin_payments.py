from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.admin_payments import (
    PAYMENTS_PER_PAGE,
    payment_detail_keyboard,
    payment_detail_text,
    payments_list_text,
    pending_payments_list_keyboard,
)
from bot.context import AppContext
from bot.db import Repository
from bot.formatting import with_footer
from bot.handlers.admin import _edit_callback_message
from bot.keyboards import admin_back_keyboard

router = Router()


def _is_admin(callback: CallbackQuery, ctx: AppContext) -> bool:
    return callback.from_user is not None and callback.from_user.id in ctx.settings.admin_ids


async def _render_payments_list_message(message: Message, ctx: AppContext, *, page: int = 1) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        total = await repository.count_pending_payments()
        items = await repository.list_pending_payments_page(page=page, per_page=PAYMENTS_PER_PAGE)
    if total == 0:
        await message.answer(with_footer("پرداخت در انتظاری وجود ندارد."), reply_markup=admin_back_keyboard())
        return
    await message.answer(
        with_footer(payments_list_text(page=page, total=total)),
        reply_markup=pending_payments_list_keyboard(items=items, page=page, total=total),
    )


async def _render_payments_list(callback: CallbackQuery, ctx: AppContext, *, page: int = 1) -> None:
    async with ctx.database.session() as db:
        repository = Repository(db)
        total = await repository.count_pending_payments()
        items = await repository.list_pending_payments_page(page=page, per_page=PAYMENTS_PER_PAGE)
    if total == 0:
        await _edit_callback_message(callback, with_footer("پرداخت در انتظاری وجود ندارد."), reply_markup=admin_back_keyboard())
        return
    await _edit_callback_message(
        callback,
        with_footer(payments_list_text(page=page, total=total)),
        reply_markup=pending_payments_list_keyboard(items=items, page=page, total=total),
    )


@router.callback_query(F.data == "admin:payments")
@router.callback_query(F.data.startswith("adm:payments:page:"))
async def payments_list_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    page = 1
    if callback.data.startswith("adm:payments:page:"):
        try:
            page = max(int(callback.data.rsplit(":", 1)[-1]), 1)
        except ValueError:
            page = 1
    await _render_payments_list(callback, ctx, page=page)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^adm:pay:\d+$"))
async def payment_detail_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    payment_id = int(callback.data.rsplit(":", 1)[-1])
    async with ctx.database.session() as db:
        item = await Repository(db).get_pending_payment_view(payment_id)
    if item is None:
        await callback.answer("پرداخت پیدا نشد یا بررسی شده است.", show_alert=True)
        return
    await _edit_callback_message(
        callback,
        with_footer(payment_detail_text(item)),
        reply_markup=payment_detail_keyboard(payment_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^adm:pay:\d+:receipt$"))
async def payment_receipt_callback(callback: CallbackQuery, ctx: AppContext) -> None:
    if not _is_admin(callback, ctx):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    payment_id = int(callback.data.split(":")[2])
    async with ctx.database.session() as db:
        payment = await Repository(db).get_payment(payment_id)
    if payment is None:
        await callback.answer("پرداخت پیدا نشد.", show_alert=True)
        return
    await callback.bot.send_photo(callback.from_user.id, payment.screenshot_file_id, caption=f"رسید پرداخت #{payment.id}")
    await callback.answer()
