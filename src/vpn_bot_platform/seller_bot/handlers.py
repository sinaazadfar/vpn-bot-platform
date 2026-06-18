from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
import re

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from vpn_bot_platform.common.models import OrderType, Plan, VpnService
from vpn_bot_platform.common.qr import make_qr_png_bytes
from vpn_bot_platform.seller_bot.forced_join import missing_required_chats
from vpn_bot_platform.seller_bot.provisioning import ProvisioningService
from vpn_bot_platform.seller_bot.services import SellerContextService, WalletChargeRequest

router = Router(name="seller_button_ui")

PAGE_SIZE = 5
SEARCH_THRESHOLD = 8


class UiState(StatesGroup):
    waiting_search = State()
    waiting_coupon = State()
    waiting_wallet_amount = State()
    waiting_rejection_reason = State()
    waiting_ticket_subject = State()
    waiting_ticket_body = State()
    waiting_ticket_reply = State()
    waiting_admin_ticket_reply = State()
    waiting_receipt = State()


@dataclass(frozen=True)
class Row:
    label: str
    callback: str


def kb(rows: Sequence[Sequence[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def main_kb(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [("خرید سرویس", "plans:0"), ("تمدید سرویس", "services:0")],
        [("سرویس‌های من", "services:0"), ("سفارش‌های من", "orders")],
        [("کیف پول", "wallet"), ("تست رایگان", "trial")],
        [("پشتیبانی", "tickets:0")],
    ]
    if is_admin:
        rows.append([("پنل ادمین", "admin")])
    return kb(rows)


async def render(
    target: Message | CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    if isinstance(target, CallbackQuery):
        if target.message:
            try:
                await target.message.edit_text(text, reply_markup=markup)
                await target.answer()
                return
            except TelegramBadRequest:
                pass
        await target.answer()
        if target.message:
            await target.message.answer(text, reply_markup=markup)
        return
    await target.answer(text, reply_markup=markup)


async def notify_buyer(target: Message | CallbackQuery, buyer_telegram_id: int, text: str) -> None:
    try:
        await target.bot.send_message(buyer_telegram_id, text)
    except TelegramAPIError:
        return


def money(value: float) -> str:
    return f"{float(value):,.0f} تومان"


def traffic(plan_or_service: Plan | VpnService) -> str:
    return "نامحدود" if plan_or_service.data_limit_gb is None else f"{plan_or_service.data_limit_gb} گیگ"


def order_status_label(status: str) -> str:
    return {
        "waiting_payment": "در انتظار پرداخت",
        "waiting_approval": "در انتظار بررسی",
        "provisioning": "در حال ساخت سرویس",
        "completed": "تکمیل شده",
        "canceled": "لغو شده",
        "failed": "ناموفق",
    }.get(status, status)


def payment_status_label(status: str) -> str:
    return {
        "pending": "در انتظار بررسی",
        "approved": "تایید شده",
        "rejected": "رد شده",
        "refunded": "بازگشت داده شده",
    }.get(status, status)


def _normalize_service_username(value: str) -> str | None:
    username = value.strip().removeprefix("@").lower()
    if len(username) < 3 or username.startswith("_") or username.endswith("_"):
        return None
    if not re.fullmatch(r"[a-z0-9_]+", username):
        return None
    return username


def paginate[T](items: Sequence[T], page: int) -> tuple[list[T], int, int]:
    total_pages = max(1, ceil(len(items) / PAGE_SIZE))
    safe_page = min(max(page, 0), total_pages - 1)
    start = safe_page * PAGE_SIZE
    return list(items[start : start + PAGE_SIZE]), safe_page, total_pages


def list_kb(
    *,
    rows: list[Row],
    page: int,
    total_pages: int,
    page_prefix: str,
    search: str | None = None,
) -> InlineKeyboardMarkup:
    buttons: list[list[tuple[str, str]]] = [[(row.label, row.callback)] for row in rows]
    nav: list[tuple[str, str]] = []
    if page > 0:
        nav.append(("قبلی", f"{page_prefix}:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(("بعدی", f"{page_prefix}:{page + 1}"))
    if nav:
        buttons.append(nav)
    tools: list[tuple[str, str]] = []
    if search:
        tools.append(("جستجو", f"search:{search}"))
    tools.append(("خانه", "home"))
    buttons.append(tools)
    return kb(buttons)


async def show_home(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    user_id: int,
) -> None:
    is_admin = False
    try:
        await seller_context.list_pending_payments(admin_telegram_id=user_id)
        is_admin = True
    except PermissionError:
        is_admin = False
    await render(
        target,
        "به پنل سرویس VPN خوش آمدید.\nیکی از گزینه‌های زیر را انتخاب کنید:",
        main_kb(is_admin=is_admin),
    )


async def blocked_message(target: Message | CallbackQuery) -> bool:
    user = target.from_user
    bot = target.bot
    if user is None:
        return True
    missing = await missing_required_chats(bot, user_id=user.id)
    if not missing:
        return False
    lines = ["برای استفاده از ربات، ابتدا عضو کانال/گروه‌های زیر شوید:"]
    for chat in missing:
        lines.append(f"- {chat.title or chat.chat_id}")
    await render(target, "\n".join(lines), kb([[("بررسی عضویت", "home")]]))
    return True


@router.message(CommandStart())
async def start(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.clear()
    if await blocked_message(message):
        return
    await seller_context.register_buyer(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )
    await show_home(message, seller_context, message.from_user.id)


@router.message(Command("admin"))
async def admin_command(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    await state.clear()
    await admin_dashboard(message, seller_context)


@router.message(Command("cancel"))
async def cancel(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.clear()
    await render(message, "عملیات لغو شد.")
    await show_home(message, seller_context, message.from_user.id)


@router.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery, seller_context: SellerContextService, state: FSMContext) -> None:
    if callback.from_user is None:
        return
    await state.clear()
    if await blocked_message(callback):
        return
    await show_home(callback, seller_context, callback.from_user.id)


@router.callback_query(F.data.startswith("plans:"))
async def plans_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if await blocked_message(callback):
        return
    page = int((callback.data or "plans:0").split(":")[1])
    plans = await seller_context.list_plans()
    await show_plans(callback, plans, page)


async def show_plans(target: Message | CallbackQuery, plans: list[Plan], page: int, query: str | None = None) -> None:
    if query:
        normalized = query.casefold()
        plans = [plan for plan in plans if normalized in plan.name.casefold() or normalized in plan.id]
    if not plans:
        await render(target, "فعلا پلنی برای نمایش وجود ندارد.", kb([[("خانه", "home")]]))
        return
    page_items, safe_page, total_pages = paginate(plans, page)
    lines = ["پلن مورد نظر را انتخاب کنید:"]
    rows = []
    for plan in page_items:
        lines.append(f"{plan.name} | {money(plan.price)} | {plan.duration_days} روز | {traffic(plan)}")
        rows.append(Row(f"{plan.name} - {money(plan.price)}", f"plan:{plan.id}"))
    await render(
        target,
        "\n".join(lines),
        list_kb(
            rows=rows,
            page=safe_page,
            total_pages=total_pages,
            page_prefix="plans",
            search="plans" if len(plans) > SEARCH_THRESHOLD else None,
        ),
    )


@router.callback_query(F.data.startswith("plan:"))
async def plan_detail(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    plan_id = (callback.data or "").split(":", 1)[1]
    plan = next((item for item in await seller_context.list_plans() if item.id == plan_id), None)
    if plan is None:
        await render(callback, "این پلن پیدا نشد.", kb([[("بازگشت", "plans:0")]]))
        return
    await render(
        callback,
        "\n".join(
            [
                f"پلن: {plan.name}",
                f"قیمت: {money(plan.price)}",
                f"مدت: {plan.duration_days} روز",
                f"حجم: {traffic(plan)}",
                "",
                "برای ثبت سفارش، یکی از گزینه‌ها را انتخاب کنید.",
            ]
        ),
        kb(
            [
                [("خرید بدون کد تخفیف", f"buy:{plan.id}")],
                [("وارد کردن کد تخفیف", f"coupon:new:{plan.id}")],
                [("بازگشت", "plans:0"), ("خانه", "home")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("buy:"))
async def buy_callback(callback: CallbackQuery, seller_context: SellerContextService, state: FSMContext) -> None:
    await create_payment_request(callback, seller_context, state, plan_id=(callback.data or "").split(":", 1)[1])


@router.callback_query(F.data.startswith("coupon:"))
async def coupon_callback(callback: CallbackQuery, state: FSMContext) -> None:
    _, mode, item_id = (callback.data or "").split(":", 2)
    await state.set_state(UiState.waiting_coupon)
    await state.update_data(coupon_mode=mode, coupon_item_id=item_id)
    await render(callback, "کد تخفیف را ارسال کنید.\nبرای لغو، /cancel را بزنید.")


@router.message(UiState.waiting_coupon, F.text)
async def coupon_text(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    data = await state.get_data()
    coupon_code = (message.text or "").strip()
    if data.get("coupon_mode") == "renew":
        await create_payment_request(
            message,
            seller_context,
            state,
            plan_id=str(data["coupon_item_id"]),
            coupon_code=coupon_code,
            service_id=str(data["service_id"]),
        )
        return
    await create_payment_request(
        message,
        seller_context,
        state,
        plan_id=str(data["coupon_item_id"]),
        coupon_code=coupon_code,
    )


async def create_payment_request(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    state: FSMContext,
    *,
    plan_id: str,
    coupon_code: str | None = None,
    service_id: str | None = None,
) -> None:
    user = target.from_user
    if user is None:
        return
    try:
        if service_id:
            request = await seller_context.request_renewal_payment(
                buyer_telegram_id=user.id,
                service_id=service_id,
                plan_id=plan_id,
                coupon_code=coupon_code,
            )
            title = "درخواست تمدید ثبت شد."
        else:
            request = await seller_context.request_card_to_card_payment(
                buyer_telegram_id=user.id,
                plan_id=plan_id,
                coupon_code=coupon_code,
            )
            title = "درخواست خرید ثبت شد."
    except ValueError as exc:
        messages = {
            "plan_not_found": "پلن پیدا نشد یا فعال نیست.",
            "service_not_found": "سرویس انتخاب‌شده پیدا نشد.",
            "discount_not_found": "کد تخفیف معتبر نیست.",
            "seller_bot_not_found": "تنظیمات ربات فروشنده کامل نیست.",
        }
        await render(target, messages.get(str(exc), "در ثبت درخواست مشکلی پیش آمد."), kb([[("خانه", "home")]]))
        return
    await state.set_state(UiState.waiting_receipt)
    await state.update_data(receipt_kind="payment", receipt_id=request.payment.id)
    await render(
        target,
        "\n".join(
            [
                title,
                f"پلن: {request.plan.name}",
                f"مبلغ: {money(request.payment.amount)}",
                f"کد پرداخت: {request.payment.id}",
                "",
                request.instructions,
                "",
                "بعد از پرداخت، عکس یا فایل رسید را همینجا ارسال کنید.",
            ]
        ),
        kb([[("بعدا ارسال می‌کنم", "home")]]),
    )


@router.callback_query(F.data.startswith("services:"))
async def services_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    page = int((callback.data or "services:0").split(":")[1])
    await show_services(callback, seller_context, callback.from_user.id, page)


@router.callback_query(F.data == "orders")
async def orders_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    orders = await seller_context.list_buyer_order_statuses(
        buyer_telegram_id=callback.from_user.id,
        limit=10,
    )
    if not orders:
        await render(callback, "هنوز سفارشی ثبت نشده است.", kb([[("خرید سرویس", "plans:0"), ("خانه", "home")]]))
        return
    rows = []
    lines = ["آخرین سفارش‌های شما:"]
    for item in orders:
        plan_name = item.plan.name if item.plan else "بدون پلن"
        amount = money(item.payment.amount) if item.payment else money(item.order.total_amount)
        lines.append(f"{plan_name} | {amount} | {order_status_label(item.order.status)}")
        rows.append([(f"{plan_name} - {order_status_label(item.order.status)}", f"order:{item.order.id}")])
    rows.append([("خانه", "home")])
    await render(callback, "\n".join(lines), kb(rows))


@router.callback_query(F.data.startswith("order:"))
async def order_detail(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    order_id = (callback.data or "").split(":", 1)[1]
    try:
        item = await seller_context.get_buyer_order_status(
            buyer_telegram_id=callback.from_user.id,
            order_id=order_id,
        )
    except ValueError:
        await render(callback, "سفارش پیدا نشد.", kb([[("سفارش‌های من", "orders"), ("خانه", "home")]]))
        return
    plan_name = item.plan.name if item.plan else "بدون پلن"
    payment = item.payment
    receipt = "دارد" if payment and payment.proof_file_id else "ندارد"
    lines = [
        f"کد سفارش: {item.order.id}",
        f"پلن: {plan_name}",
        f"مبلغ: {money(payment.amount if payment else item.order.total_amount)}",
        f"وضعیت سفارش: {order_status_label(item.order.status)}",
    ]
    if payment:
        lines.extend(
            [
                f"کد پرداخت: {payment.id}",
                f"روش پرداخت: {payment.method}",
                f"وضعیت پرداخت: {payment_status_label(payment.status)}",
                f"رسید: {receipt}",
            ]
        )
        if payment.rejection_reason:
            lines.extend(["", f"دلیل رد پرداخت: {payment.rejection_reason}"])
    await render(
        callback,
        "\n".join(lines),
        kb([[("بازگشت به سفارش‌ها", "orders"), ("خانه", "home")]]),
    )


async def show_services(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    user_id: int,
    page: int,
    query: str | None = None,
) -> None:
    services = await seller_context.list_buyer_services(buyer_telegram_id=user_id)
    if query:
        normalized = query.casefold()
        services = [
            service
            for service in services
            if normalized in service.id or normalized in service.marzban_username.casefold()
        ]
    if not services:
        await render(target, "هنوز سرویسی ندارید.", kb([[("خرید سرویس", "plans:0"), ("خانه", "home")]]))
        return
    page_items, safe_page, total_pages = paginate(services, page)
    rows = [Row(f"{service.marzban_username} - {traffic(service)}", f"svc:{service.id}") for service in page_items]
    await render(
        target,
        "سرویس مورد نظر را انتخاب کنید:",
        list_kb(
            rows=rows,
            page=safe_page,
            total_pages=total_pages,
            page_prefix="services",
            search="services" if len(services) > SEARCH_THRESHOLD else None,
        ),
    )


@router.callback_query(F.data.startswith("svc:"))
async def service_detail(callback: CallbackQuery, seller_context: SellerContextService, state: FSMContext) -> None:
    if callback.from_user is None:
        return
    service_id = (callback.data or "").split(":", 1)[1]
    services = await seller_context.list_buyer_services(buyer_telegram_id=callback.from_user.id)
    service = next((item for item in services if item.id == service_id), None)
    if service is None:
        await render(callback, "سرویس پیدا نشد.", kb([[("بازگشت", "services:0")]]))
        return
    await state.update_data(service_id=service.id)
    expire = service.expire_at.strftime("%Y-%m-%d") if service.expire_at else "نامحدود"
    await render(
        callback,
        "\n".join(
            [
                f"نام کاربری: {service.marzban_username}",
                f"حجم: {traffic(service)}",
                f"انقضا: {expire}",
                f"وضعیت: {'فعال' if service.is_active else 'غیرفعال'}",
                f"لینک اشتراک: {service.subscription_url or '-'}",
            ]
        ),
        kb(
            [
                [("تمدید این سرویس", f"renewsvc:{service.id}")],
                [("تعویض لینک اشتراک", f"revokeask:{service.id}")],
                [("بازگشت", "services:0"), ("خانه", "home")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("revokeask:"))
async def revoke_subscription_ask(callback: CallbackQuery) -> None:
    service_id = (callback.data or "").split(":", 1)[1]
    await render(
        callback,
        "\n".join(
            [
                "با تعویض لینک اشتراک، لینک قبلی دیگر قابل استفاده نیست.",
                "این کار برای وقتی خوب است که لینک شما لو رفته یا روی دستگاه دیگری مانده باشد.",
                "",
                "ادامه می‌دهید؟",
            ]
        ),
        kb([[("بله، تعویض کن", f"revokesub:{service_id}")], [("لغو", f"svc:{service_id}")]]),
    )


@router.callback_query(F.data.startswith("revokesub:"))
async def revoke_subscription_confirm(
    callback: CallbackQuery,
    provisioning_service: ProvisioningService,
) -> None:
    if callback.from_user is None:
        return
    service_id = (callback.data or "").split(":", 1)[1]
    try:
        service = await provisioning_service.revoke_subscription_link(
            buyer_telegram_id=callback.from_user.id,
            service_id=service_id,
        )
    except ValueError as exc:
        messages = {
            "service_not_found": "سرویس پیدا نشد.",
            "panel_not_found": "پنل این سرویس در دسترس نیست.",
            "subscription_url_not_returned": "لینک جدید از پنل دریافت نشد.",
        }
        await render(
            callback,
            messages.get(str(exc), "تعویض لینک انجام نشد."),
            kb([[("بازگشت", f"svc:{service_id}"), ("خانه", "home")]]),
        )
        return
    text = "\n".join(
        [
            "لینک اشتراک با موفقیت تعویض شد.",
            f"نام کاربری: {service.marzban_username}",
            f"لینک جدید: {service.subscription_url}",
        ]
    )
    if service.subscription_url and callback.message:
        qr_file = BufferedInputFile(
            make_qr_png_bytes(service.subscription_url),
            filename=f"{service.marzban_username}.png",
        )
        await callback.message.answer_photo(
            qr_file,
            caption=text,
            reply_markup=kb([[("بازگشت به سرویس", f"svc:{service.id}"), ("خانه", "home")]]),
        )
        await callback.answer()
        return
    await render(callback, text, kb([[("بازگشت به سرویس", f"svc:{service.id}"), ("خانه", "home")]]))


@router.callback_query(F.data.startswith("renewsvc:"))
async def renew_service(callback: CallbackQuery, seller_context: SellerContextService, state: FSMContext) -> None:
    service_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(service_id=service_id)
    await show_renew_plans(callback, seller_context, 0)


@router.callback_query(F.data.startswith("renewplans:"))
async def renew_plans_page(
    callback: CallbackQuery,
    seller_context: SellerContextService,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    if not data.get("service_id"):
        await render(callback, "ابتدا سرویس را انتخاب کنید.", kb([[("سرویس‌های من", "services:0")]]))
        return
    page = int((callback.data or "renewplans:0").split(":")[1])
    await show_renew_plans(callback, seller_context, page)


async def show_renew_plans(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    page: int,
) -> None:
    plans = await seller_context.list_plans()
    if not plans:
        await render(target, "فعلا پلنی برای تمدید وجود ندارد.", kb([[("خانه", "home")]]))
        return
    page_items, safe_page, total_pages = paginate(plans, page)
    rows = [Row(f"{plan.name} - {money(plan.price)}", f"renew:{plan.id}") for plan in page_items]
    await render(
        target,
        "پلن تمدید را انتخاب کنید:",
        list_kb(rows=rows, page=safe_page, total_pages=total_pages, page_prefix="renewplans"),
    )


@router.callback_query(F.data.startswith("renew:"))
async def renew_plan(callback: CallbackQuery, seller_context: SellerContextService, state: FSMContext) -> None:
    data = await state.get_data()
    plan_id = (callback.data or "").split(":", 1)[1]
    service_id = str(data.get("service_id", ""))
    if not service_id:
        await render(callback, "ابتدا سرویس را انتخاب کنید.", kb([[("سرویس‌های من", "services:0")]]))
        return
    await render(
        callback,
        "تمدید با کد تخفیف انجام شود؟",
        kb(
            [
                [("بدون کد تخفیف", f"renewpay:{plan_id}")],
                [("وارد کردن کد تخفیف", f"coupon:renew:{plan_id}")],
                [("بازگشت", "services:0")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("renewpay:"))
async def renew_pay(callback: CallbackQuery, seller_context: SellerContextService, state: FSMContext) -> None:
    data = await state.get_data()
    await create_payment_request(
        callback,
        seller_context,
        state,
        plan_id=(callback.data or "").split(":", 1)[1],
        service_id=str(data.get("service_id", "")),
    )


@router.callback_query(F.data == "wallet")
async def wallet_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    wallet_info = await seller_context.list_buyer_wallet(buyer_telegram_id=callback.from_user.id)
    balance = float(wallet_info.buyer.wallet_balance) if wallet_info.buyer else 0
    lines = [f"موجودی کیف پول: {money(balance)}", "", "شارژهای اخیر:"]
    if not wallet_info.transactions:
        lines.append("موردی ثبت نشده است.")
    for transaction in wallet_info.transactions[:5]:
        lines.append(f"{money(transaction.amount)} | {transaction.status}")
    await render(
        callback,
        "\n".join(lines),
        kb(
            [
                [("شارژ ۱۰۰ هزار", "charge:100000"), ("شارژ ۲۰۰ هزار", "charge:200000")],
                [("مبلغ دلخواه", "charge:custom")],
                [("خانه", "home")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("charge:"))
async def charge_callback(callback: CallbackQuery, seller_context: SellerContextService, state: FSMContext) -> None:
    value = (callback.data or "").split(":", 1)[1]
    if value == "custom":
        await state.set_state(UiState.waiting_wallet_amount)
        await render(callback, "مبلغ شارژ را به تومان ارسال کنید.\nبرای لغو، /cancel را بزنید.")
        return
    await create_wallet_charge(callback, seller_context, state, float(value))


@router.message(UiState.waiting_wallet_amount, F.text)
async def wallet_amount_text(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    raw = (message.text or "").replace(",", "").strip()
    try:
        amount = float(raw)
    except ValueError:
        await render(message, "مبلغ معتبر نیست. فقط عدد ارسال کنید.")
        return
    await create_wallet_charge(message, seller_context, state, amount)


async def create_wallet_charge(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    state: FSMContext,
    amount: float,
) -> None:
    if target.from_user is None:
        return
    try:
        charge = await seller_context.request_wallet_charge(
            buyer_telegram_id=target.from_user.id,
            amount=amount,
        )
    except ValueError:
        await render(target, "مبلغ باید بیشتر از صفر باشد.")
        return
    await state.set_state(UiState.waiting_receipt)
    await state.update_data(receipt_kind="wallet", receipt_id=charge.transaction.id)
    await render_receipt_prompt(target, charge)


async def render_receipt_prompt(target: Message | CallbackQuery, charge: WalletChargeRequest) -> None:
    await render(
        target,
        "\n".join(
            [
                "درخواست شارژ کیف پول ثبت شد.",
                f"مبلغ: {money(charge.transaction.amount)}",
                f"کد تراکنش: {charge.transaction.id}",
                "",
                charge.instructions,
                "",
                "بعد از پرداخت، عکس یا فایل رسید را همینجا ارسال کنید.",
            ]
        ),
        kb([[("بعدا ارسال می‌کنم", "home")]]),
    )


@router.message(UiState.waiting_receipt, F.photo | F.document)
async def receipt_upload(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    if message.from_user is None:
        return
    file_id = message.document.file_id if message.document else message.photo[-1].file_id
    data = await state.get_data()
    try:
        if data.get("receipt_kind") == "wallet":
            await seller_context.attach_wallet_charge_receipt(
                buyer_telegram_id=message.from_user.id,
                transaction_id=str(data["receipt_id"]),
                file_id=file_id,
            )
        else:
            await seller_context.attach_payment_receipt(
                buyer_telegram_id=message.from_user.id,
                payment_id=str(data["receipt_id"]),
                file_id=file_id,
            )
    except ValueError:
        await render(message, "رسید برای این درخواست ثبت نشد. لطفا دوباره از منو اقدام کنید.")
        await state.clear()
        return
    await state.clear()
    await render(message, "رسید دریافت شد. بعد از بررسی ادمین، وضعیت سفارش به‌روزرسانی می‌شود.", kb([[("خانه", "home")]]))


@router.message(UiState.waiting_receipt)
async def receipt_invalid(message: Message) -> None:
    await render(message, "لطفا عکس یا فایل رسید را ارسال کنید.")


@router.callback_query(F.data == "trial")
async def trial_callback(callback: CallbackQuery, provisioning_service: ProvisioningService) -> None:
    if callback.from_user is None:
        return
    try:
        service = await provisioning_service.provision_trial(
            buyer_telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            language_code=callback.from_user.language_code,
        )
    except ValueError as exc:
        messages = {
            "trial_disabled": "تست رایگان فعلا فعال نیست.",
            "trial_already_used": "شما قبلا تست رایگان خود را دریافت کرده‌اید.",
            "panel_assignment_not_found": "برای این فروشنده پنل فعالی تنظیم نشده است.",
        }
        await render(callback, messages.get(str(exc), "ساخت تست رایگان انجام نشد."), kb([[("خانه", "home")]]))
        return
    text = "\n".join(
        [
            "تست رایگان ساخته شد.",
            f"نام کاربری: {service.marzban_username}",
            f"حجم: {traffic(service)}",
            f"لینک اشتراک: {service.subscription_url or '-'}",
        ]
    )
    if service.subscription_url and callback.message:
        qr_file = BufferedInputFile(
            make_qr_png_bytes(service.subscription_url),
            filename=f"{service.marzban_username}.png",
        )
        await callback.message.answer_photo(qr_file, caption=text, reply_markup=kb([[("خانه", "home")]]))
        await callback.answer()
        return
    await render(callback, text, kb([[("خانه", "home")]]))


@router.callback_query(F.data.startswith("tickets:"))
async def tickets_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    page = int((callback.data or "tickets:0").split(":")[1])
    await show_tickets(callback, seller_context, callback.from_user.id, page)


async def show_tickets(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    user_id: int,
    page: int,
    query: str | None = None,
) -> None:
    tickets = await seller_context.list_my_tickets(buyer_telegram_id=user_id)
    if query:
        normalized = query.casefold()
        tickets = [ticket for ticket in tickets if normalized in ticket.subject.casefold() or normalized in ticket.id]
    page_items, safe_page, total_pages = paginate(tickets, page)
    rows = [Row(f"{ticket.subject} - {ticket.status}", f"ticket:{ticket.id}") for ticket in page_items]
    buttons = list_kb(
        rows=rows,
        page=safe_page,
        total_pages=total_pages,
        page_prefix="tickets",
        search="buyer_tickets" if len(tickets) > SEARCH_THRESHOLD else None,
    ).inline_keyboard
    buttons.insert(0, [InlineKeyboardButton(text="ثبت تیکت جدید", callback_data="ticket:new")])
    await render(target, "تیکت‌های شما:", InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data == "ticket:new")
async def ticket_new(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(UiState.waiting_ticket_subject)
    await render(callback, "موضوع تیکت را کوتاه ارسال کنید.\nبرای لغو، /cancel را بزنید.")


@router.message(UiState.waiting_ticket_subject, F.text)
async def ticket_subject(message: Message, state: FSMContext) -> None:
    await state.update_data(ticket_subject=(message.text or "").strip())
    await state.set_state(UiState.waiting_ticket_body)
    await render(message, "متن پیام را ارسال کنید.")


@router.message(UiState.waiting_ticket_body, F.text)
async def ticket_body(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    thread = await seller_context.open_ticket(
        buyer_telegram_id=message.from_user.id,
        subject=str(data.get("ticket_subject", "پشتیبانی")),
        body=(message.text or "").strip(),
    )
    await state.clear()
    await render(message, f"تیکت ثبت شد.\nکد تیکت: {thread.ticket.id}", kb([[("تیکت‌ها", "tickets:0"), ("خانه", "home")]]))


@router.callback_query(F.data.startswith("ticket:"))
async def ticket_detail(callback: CallbackQuery, state: FSMContext) -> None:
    ticket_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(ticket_id=ticket_id)
    await render(
        callback,
        f"کد تیکت: {ticket_id}",
        kb([[("ارسال پاسخ", f"ticketreply:{ticket_id}")], [("بازگشت", "tickets:0"), ("خانه", "home")]]),
    )


@router.callback_query(F.data.startswith("ticketreply:"))
async def ticket_reply_callback(callback: CallbackQuery, state: FSMContext) -> None:
    ticket_id = (callback.data or "").split(":", 1)[1]
    await state.set_state(UiState.waiting_ticket_reply)
    await state.update_data(ticket_id=ticket_id)
    await render(callback, "متن پاسخ را ارسال کنید.")


@router.message(UiState.waiting_ticket_reply, F.text)
async def ticket_reply_text(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    try:
        await seller_context.reply_ticket_as_buyer(
            buyer_telegram_id=message.from_user.id,
            ticket_id=str(data["ticket_id"]),
            body=(message.text or "").strip(),
        )
    except ValueError:
        await render(message, "تیکت پیدا نشد.")
        return
    await state.clear()
    await render(message, "پاسخ شما ثبت شد.", kb([[("تیکت‌ها", "tickets:0"), ("خانه", "home")]]))


@router.callback_query(F.data == "admin")
async def admin_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    await admin_dashboard(callback, seller_context)


async def admin_dashboard(target: Message | CallbackQuery, seller_context: SellerContextService) -> None:
    if target.from_user is None:
        return
    try:
        pending = await seller_context.list_pending_payments(admin_telegram_id=target.from_user.id)
        wallet = await seller_context.list_pending_wallet_charges(admin_telegram_id=target.from_user.id)
        tickets = await seller_context.list_open_tickets(admin_telegram_id=target.from_user.id)
    except PermissionError:
        await render(target, "شما دسترسی ادمین فروشنده ندارید.", kb([[("خانه", "home")]]))
        return
    await render(
        target,
        "\n".join(
            [
                "پنل ادمین فروشنده",
                f"پرداخت‌های در انتظار: {len(pending)}",
                f"شارژهای کیف پول: {len(wallet)}",
                f"تیکت‌های باز: {len(tickets)}",
            ]
        ),
        kb(
            [
                [("پرداخت‌ها", "admin:payments:0"), ("شارژ کیف پول", "admin:wallet:0")],
                [("تیکت‌ها", "admin:tickets:0"), ("گزارش فروش", "admin:report")],
                [("خانه", "home")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("admin:payments:"))
async def admin_payments(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    page = int((callback.data or "admin:payments:0").split(":")[2])
    await show_admin_payments(callback, seller_context, page)


async def show_admin_payments(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    page: int,
    query: str | None = None,
) -> None:
    if target.from_user is None:
        return
    try:
        items = await seller_context.list_pending_payments(admin_telegram_id=target.from_user.id)
    except PermissionError:
        await render(target, "دسترسی ندارید.", kb([[("خانه", "home")]]))
        return
    if query:
        normalized = query.casefold()
        items = [
            item
            for item in items
            if normalized in item.payment.id or normalized in item.order.id or normalized in item.plan.name.casefold()
        ]
    page_items, safe_page, total_pages = paginate(items, page)
    rows = [
        Row(f"{item.plan.name} - {money(item.payment.amount)}", f"adminpay:{item.payment.id}")
        for item in page_items
    ]
    await render(
        target,
        "پرداخت‌های در انتظار:",
        list_kb(
            rows=rows,
            page=safe_page,
            total_pages=total_pages,
            page_prefix="admin:payments",
            search="payments" if len(items) > SEARCH_THRESHOLD else None,
        ),
    )


@router.callback_query(F.data.startswith("adminpay:"))
async def admin_payment_detail(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    payment_id = (callback.data or "").split(":", 1)[1]
    if callback.from_user is None:
        return
    pending = await seller_context.list_pending_payments(admin_telegram_id=callback.from_user.id)
    item = next((payment for payment in pending if payment.payment.id == payment_id), None)
    if item is None:
        await render(callback, "پرداخت پیدا نشد.", kb([[("بازگشت", "admin:payments:0")]]))
        return
    receipt = "دارد" if item.payment.proof_file_id else "ندارد"
    await render(
        callback,
        "\n".join(
            [
                f"پلن: {item.plan.name}",
                f"مبلغ: {money(item.payment.amount)}",
                f"رسید: {receipt}",
                f"کد سفارش: {item.order.id}",
                f"کد پرداخت: {item.payment.id}",
            ]
        ),
        kb(
            [
                [("تایید پرداخت", f"approvepay:{item.payment.id}")],
                [("رد پرداخت", f"rejectpay:{item.payment.id}")],
                [("بازگشت", "admin:payments:0")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("rejectpay:"))
async def reject_payment_callback(callback: CallbackQuery, state: FSMContext) -> None:
    payment_id = (callback.data or "").split(":", 1)[1]
    await state.set_state(UiState.waiting_rejection_reason)
    await state.update_data(reject_payment_id=payment_id)
    await render(callback, "دلیل رد پرداخت را کوتاه ارسال کنید.\nبرای لغو، /cancel را بزنید.")


@router.message(UiState.waiting_rejection_reason, F.text)
async def rejection_reason_text(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    reason = (message.text or "").strip()
    if not reason:
        await render(message, "دلیل رد پرداخت نمی‌تواند خالی باشد.")
        return
    data = await state.get_data()
    try:
        rejected = await seller_context.reject_payment(
            admin_telegram_id=message.from_user.id,
            payment_id=str(data["reject_payment_id"]),
            reason=reason,
        )
    except (PermissionError, ValueError):
        await render(message, "پرداخت قابل رد کردن نیست.", kb([[("پرداخت‌ها", "admin:payments:0")]]))
        return
    await state.clear()
    await notify_buyer(
        message,
        rejected.buyer.telegram_user_id,
        "\n".join(
            [
                "پرداخت شما رد شد.",
                f"کد سفارش: {rejected.order.id}",
                f"دلیل: {rejected.payment.rejection_reason}",
                "",
                "برای مشاهده جزئیات از بخش «سفارش‌های من» استفاده کنید.",
            ]
        ),
    )
    await render(
        message,
        f"پرداخت رد شد.\nکد سفارش: {rejected.order.id}\nدلیل: {rejected.payment.rejection_reason}",
        kb([[("پرداخت‌ها", "admin:payments:0"), ("پنل ادمین", "admin")]]),
    )


@router.callback_query(F.data.startswith("approvepay:"))
async def approve_payment_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    payment_id = (callback.data or "").split(":", 1)[1]
    try:
        approved = await seller_context.approve_payment(
            admin_telegram_id=callback.from_user.id,
            payment_id=payment_id,
        )
    except (PermissionError, ValueError):
        await render(callback, "پرداخت قابل تایید نیست.", kb([[("بازگشت", "admin:payments:0")]]))
        return
    await notify_buyer(
        callback,
        approved.buyer.telegram_user_id,
        "\n".join(
            [
                "پرداخت شما تایید شد.",
                f"کد سفارش: {approved.order.id}",
                "سرویس شما در حال ساخت است.",
                "",
                "برای پیگیری وضعیت از بخش «سفارش‌های من» استفاده کنید.",
            ]
        ),
    )
    action = "applyrenew" if approved.order.order_type == OrderType.RENEWAL.value else "provision"
    label = "اعمال تمدید" if action == "applyrenew" else "ساخت سرویس"
    await render(
        callback,
        f"پرداخت تایید شد.\nکد سفارش: {approved.order.id}",
        kb([[ (label, f"{action}:{approved.order.id}") ], [("پنل ادمین", "admin")]]),
    )


@router.callback_query(F.data.startswith("provision:"))
async def provision_callback(callback: CallbackQuery, provisioning_service: ProvisioningService) -> None:
    if callback.from_user is None:
        return
    order_id = (callback.data or "").split(":", 1)[1]
    try:
        provisioned = await provisioning_service.provision_order(
            admin_telegram_id=callback.from_user.id,
            order_id=order_id,
        )
    except (PermissionError, ValueError):
        await render(callback, "ساخت سرویس انجام نشد.", kb([[("پنل ادمین", "admin")]]))
        return
    text = f"سرویس ساخته شد.\nنام کاربری: {provisioned.vpn_service.marzban_username}"
    if provisioned.vpn_service.subscription_url and callback.message:
        qr_file = BufferedInputFile(
            make_qr_png_bytes(provisioned.vpn_service.subscription_url),
            filename=f"{provisioned.vpn_service.marzban_username}.png",
        )
        await callback.message.answer_photo(qr_file, caption=text, reply_markup=kb([[("پنل ادمین", "admin")]]))
        await callback.answer()
        return
    await render(callback, text, kb([[("پنل ادمین", "admin")]]))


@router.callback_query(F.data.startswith("applyrenew:"))
async def apply_renew_callback(callback: CallbackQuery, provisioning_service: ProvisioningService) -> None:
    if callback.from_user is None:
        return
    try:
        renewed = await provisioning_service.apply_renewal(
            admin_telegram_id=callback.from_user.id,
            order_id=(callback.data or "").split(":", 1)[1],
        )
    except (PermissionError, ValueError):
        await render(callback, "تمدید انجام نشد.", kb([[("پنل ادمین", "admin")]]))
        return
    await render(
        callback,
        f"تمدید انجام شد.\nنام کاربری: {renewed.vpn_service.marzban_username}",
        kb([[("پنل ادمین", "admin")]]),
    )


@router.callback_query(F.data.startswith("admin:wallet:"))
async def admin_wallet(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    page = int((callback.data or "admin:wallet:0").split(":")[2])
    await show_admin_wallet(callback, seller_context, page)


async def show_admin_wallet(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    page: int,
    query: str | None = None,
) -> None:
    if target.from_user is None:
        return
    items = await seller_context.list_pending_wallet_charges(admin_telegram_id=target.from_user.id)
    if query:
        normalized = query.casefold()
        items = [item for item in items if normalized in item.id or normalized in str(item.owner_id)]
    page_items, safe_page, total_pages = paginate(items, page)
    rows = [
        Row(f"{money(item.amount)} | رسید: {'دارد' if item.proof_file_id else 'ندارد'}", f"admintx:{item.id}")
        for item in page_items
    ]
    await render(
        target,
        "شارژهای کیف پول در انتظار:",
        list_kb(
            rows=rows,
            page=safe_page,
            total_pages=total_pages,
            page_prefix="admin:wallet",
            search="wallet" if len(items) > SEARCH_THRESHOLD else None,
        ),
    )


@router.callback_query(F.data.startswith("admintx:"))
async def admin_wallet_detail(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    tx_id = (callback.data or "").split(":", 1)[1]
    items = await seller_context.list_pending_wallet_charges(admin_telegram_id=callback.from_user.id)
    item = next((tx for tx in items if tx.id == tx_id), None)
    if item is None:
        await render(callback, "تراکنش پیدا نشد.", kb([[("بازگشت", "admin:wallet:0")]]))
        return
    await render(
        callback,
        f"مبلغ: {money(item.amount)}\nرسید: {'دارد' if item.proof_file_id else 'ندارد'}\nکد تراکنش: {item.id}",
        kb([[("تایید شارژ", f"approvetx:{item.id}")], [("بازگشت", "admin:wallet:0")]]),
    )


@router.callback_query(F.data.startswith("approvetx:"))
async def approve_wallet_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    try:
        await seller_context.approve_wallet_charge(
            admin_telegram_id=callback.from_user.id,
            transaction_id=(callback.data or "").split(":", 1)[1],
        )
    except (PermissionError, ValueError):
        await render(callback, "شارژ قابل تایید نیست.", kb([[("پنل ادمین", "admin")]]))
        return
    await render(callback, "شارژ کیف پول تایید شد.", kb([[("پنل ادمین", "admin")]]))


@router.callback_query(F.data.startswith("admin:tickets:"))
async def admin_tickets(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    page = int((callback.data or "admin:tickets:0").split(":")[2])
    await show_admin_tickets(callback, seller_context, page)


async def show_admin_tickets(
    target: Message | CallbackQuery,
    seller_context: SellerContextService,
    page: int,
    query: str | None = None,
) -> None:
    if target.from_user is None:
        return
    tickets = await seller_context.list_open_tickets(admin_telegram_id=target.from_user.id)
    if query:
        normalized = query.casefold()
        tickets = [ticket for ticket in tickets if normalized in ticket.subject.casefold() or normalized in ticket.id]
    page_items, safe_page, total_pages = paginate(tickets, page)
    rows = [Row(f"{ticket.subject} - {ticket.status}", f"adminticket:{ticket.id}") for ticket in page_items]
    await render(
        target,
        "تیکت‌های باز:",
        list_kb(
            rows=rows,
            page=safe_page,
            total_pages=total_pages,
            page_prefix="admin:tickets",
            search="admin_tickets" if len(tickets) > SEARCH_THRESHOLD else None,
        ),
    )


@router.callback_query(F.data.startswith("adminticket:"))
async def admin_ticket_detail(callback: CallbackQuery) -> None:
    ticket_id = (callback.data or "").split(":", 1)[1]
    await render(
        callback,
        f"کد تیکت: {ticket_id}",
        kb([[("پاسخ", f"adminreply:{ticket_id}"), ("بستن", f"closeticket:{ticket_id}")], [("بازگشت", "admin:tickets:0")]]),
    )


@router.callback_query(F.data.startswith("adminreply:"))
async def admin_reply_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(UiState.waiting_admin_ticket_reply)
    await state.update_data(admin_ticket_id=(callback.data or "").split(":", 1)[1])
    await render(callback, "متن پاسخ ادمین را ارسال کنید.")


@router.message(UiState.waiting_admin_ticket_reply, F.text)
async def admin_reply_text(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    try:
        await seller_context.reply_ticket_as_admin(
            admin_telegram_id=message.from_user.id,
            ticket_id=str(data["admin_ticket_id"]),
            body=(message.text or "").strip(),
        )
    except (PermissionError, ValueError):
        await render(message, "پاسخ ثبت نشد.")
        return
    await state.clear()
    await render(message, "پاسخ ادمین ثبت شد.", kb([[("پنل ادمین", "admin")]]))


@router.callback_query(F.data.startswith("closeticket:"))
async def close_ticket_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    try:
        await seller_context.close_ticket(
            admin_telegram_id=callback.from_user.id,
            ticket_id=(callback.data or "").split(":", 1)[1],
        )
    except (PermissionError, ValueError):
        await render(callback, "تیکت بسته نشد.", kb([[("پنل ادمین", "admin")]]))
        return
    await render(callback, "تیکت بسته شد.", kb([[("پنل ادمین", "admin")]]))


@router.callback_query(F.data == "admin:report")
async def admin_report(callback: CallbackQuery) -> None:
    await render(
        callback,
        "بازه گزارش را انتخاب کنید:",
        kb([[("امروز", "report:1"), ("۷ روز", "report:7"), ("۳۰ روز", "report:30")], [("پنل ادمین", "admin")]]),
    )


@router.callback_query(F.data.startswith("report:"))
async def report_callback(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    if callback.from_user is None:
        return
    days = int((callback.data or "report:1").split(":")[1])
    report = await seller_context.sales_report(admin_telegram_id=callback.from_user.id, days=days)
    labels = {
        "completed_orders": "سفارش کامل‌شده",
        "completed_order_total": "مبلغ سفارش‌ها",
        "approved_payments": "پرداخت تاییدشده",
        "approved_payment_total": "مبلغ پرداخت‌ها",
        "new_buyers": "خریدار جدید",
        "new_services": "سرویس جدید",
        "wallet_charges": "شارژ کیف پول",
        "wallet_charge_total": "مبلغ شارژ کیف پول",
    }
    lines = [f"گزارش {days} روز اخیر"]
    for key, value in report.items():
        text = money(float(value)) if "total" in key else str(value)
        lines.append(f"{labels.get(key, key)}: {text}")
    await render(callback, "\n".join(lines), kb([[("پنل ادمین", "admin")]]))


@router.callback_query(F.data.startswith("search:"))
async def search_callback(callback: CallbackQuery, state: FSMContext) -> None:
    target = (callback.data or "").split(":", 1)[1]
    await state.set_state(UiState.waiting_search)
    await state.update_data(search_target=target)
    await render(callback, "عبارت جستجو را ارسال کنید.\nبرای لغو، /cancel را بزنید.")


@router.message(UiState.waiting_search, F.text)
async def search_text(message: Message, seller_context: SellerContextService, state: FSMContext) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    target = str(data.get("search_target"))
    query = (message.text or "").strip()
    await state.clear()
    if target == "plans":
        await show_plans(message, await seller_context.list_plans(), 0, query)
    elif target == "services":
        await show_services(message, seller_context, message.from_user.id, 0, query)
    elif target == "buyer_tickets":
        await show_tickets(message, seller_context, message.from_user.id, 0, query)
    elif target == "payments":
        await show_admin_payments(message, seller_context, 0, query)
    elif target == "wallet":
        await show_admin_wallet(message, seller_context, 0, query)
    elif target == "admin_tickets":
        await show_admin_tickets(message, seller_context, 0, query)
    else:
        await render(message, "جستجو برای این بخش فعال نیست.", kb([[("خانه", "home")]]))


@router.message()
async def unknown_message(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    await render(message, "لطفا از دکمه‌ها استفاده کنید.", main_kb())
