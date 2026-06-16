from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message, ReplyKeyboardRemove
import httpx

from vpn_bot_platform.common.qr import make_qr_png_bytes
from vpn_bot_platform.common.ui.callbacks import parse_callback
from vpn_bot_platform.common.ui.keyboards import (
    admin_order_actions,
    admin_payment_actions,
    admin_payment_settings_menu,
    admin_support_settings_menu,
    admin_customer_card_actions,
    admin_customer_detail_actions,
    admin_customers_menu,
    admin_plan_actions,
    admin_plan_list_menu,
    admin_plans_menu,
    admin_ticket_actions,
    admin_wallet_charge_actions,
    cancel_only_keyboard,
    buyer_ticket_actions,
    confirm_keyboard,
    extra_volume_confirm_menu,
    extra_volume_coupon_menu,
    extra_volume_plan_button,
    forced_join_blocked_menu,
    payment_request_actions,
    plan_list_menu,
    plan_buy_button,
    purchase_confirm_menu,
    purchase_coupon_menu,
    renewal_confirm_menu,
    renewal_coupon_menu,
    renewal_plan_button,
    renewal_plan_list_menu,
    seller_admin_menu,
    seller_buyer_menu,
    seller_report_menu,
    seller_section_menu,
    service_actions,
    service_list_menu,
    support_menu,
    wallet_charge_menu,
    wallet_charge_request_actions,
    wallet_transaction_actions,
)
from vpn_bot_platform.common.ui.messages import section, short_id, status_label, title
from vpn_bot_platform.common.models import OrderType, PlanPurpose
from vpn_bot_platform.seller_bot.forced_join import missing_required_chats
from vpn_bot_platform.seller_bot.provisioning import ProvisioningService
from vpn_bot_platform.seller_bot.services import SellerContextService

router = Router(name="seller_basic")


class TicketCreateStates(StatesGroup):
    subject = State()
    body = State()
    confirm = State()


class TicketReplyStates(StatesGroup):
    buyer_body = State()
    admin_body = State()


class WalletChargeStates(StatesGroup):
    amount = State()
    confirm = State()


class ReceiptUploadStates(StatesGroup):
    photo = State()


class PurchaseCreateStates(StatesGroup):
    username = State()
    coupon = State()
    confirm = State()


class RenewalCreateStates(StatesGroup):
    plan = State()
    coupon = State()
    confirm = State()


class ExtraVolumeCreateStates(StatesGroup):
    plan = State()
    coupon = State()
    confirm = State()


class SellerBroadcastCreateStates(StatesGroup):
    title = State()
    body = State()
    confirm = State()


class SellerReportCustomStates(StatesGroup):
    days = State()


class AdminCustomerSearchStates(StatesGroup):
    query = State()


class AdminPlanCreateStates(StatesGroup):
    name = State()
    volume = State()
    days = State()
    price = State()
    confirm = State()


class CryptoPaymentSetupStates(StatesGroup):
    currency = State()
    network = State()
    wallet_address = State()
    note = State()
    confirm = State()


class SupportSettingsStates(StatesGroup):
    telegram_id = State()


@router.message(CommandStart())
async def start(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext | None = None,
) -> None:
    if message.from_user is None:
        return
    if state is not None:
        await state.clear()
    if await _blocked_by_forced_join(message):
        return
    profile = await seller_context.register_buyer(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )
    await message.answer(
        _buyer_dashboard_text(seller_name=profile.seller_bot.name, reseller_name=profile.reseller.display_name),
        reply_markup=seller_buyer_menu(),
    )
    await message.answer("کیبورد پایین حذف شد؛ از دکمه‌های داخل پیام استفاده کنید.", reply_markup=ReplyKeyboardRemove())


@router.message(Command("cancel"))
@router.message(F.text.in_({"Cancel", "cancel", "❌ انصراف", "❌ لغو"}))
async def cancel_flow(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    await state.clear()
    profile = await seller_context.register_buyer(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )
    await message.answer(
        "\n".join([title("❌ عملیات لغو شد"), "به صفحه اصلی ربات بازگشتید.", "", f"فروشنده: {profile.reseller.display_name}"]),
        reply_markup=seller_buyer_menu(),
    )
    await message.answer("کیبورد پایین حذف شد؛ از دکمه‌های داخل پیام استفاده کنید.", reply_markup=ReplyKeyboardRemove())


@router.message(
    F.text.in_(
        {
            "Buy VPN",
            "🛒 خرید سرویس",
            "My Services",
            "🛍 سرویس های من",
            "Renew",
            "افزایش اعتبار زمانی",
            "Wallet",
            "💸 شارژ حساب",
            "👤 پروفایل",
            "Support",
            "📮 پشتیبانی آنلاین",
            "Trial",
            "🎁 سرویس تستی (رایگان)",
            "Guides",
            "🔗 راهنمای اتصال",
            "Pending Payments",
            "💳 پرداخت ها",
            "Provision Orders",
            "🧾 سفارش ها",
            "Wallet Charges",
            "💸 شارژ کیف پول",
            "Customers",
            "👤 مدیریت کاربران",
            "Tickets",
            "📮 تیکت ها",
            "Plans",
            "🛒 تعرفه خدمات",
            "Payment Method",
            "🪙 روش پرداخت",
            "Sales Report",
            "📊 گزارش فروش",
            "Buyer Home",
            "📱 منوی اصلی",
        }
    )
)
async def seller_reply_menu_alias(
    message: Message,
    seller_context: SellerContextService,
    provisioning_service: ProvisioningService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    await state.clear()
    if message.text in {"Buy VPN", "🛒 خرید سرویس"}:
        plans = await seller_context.list_plans(purpose=PlanPurpose.PURCHASE)
        await message.answer(_plans_text_from_list(plans), reply_markup=plan_list_menu(plans))
    elif message.text in {"My Services", "🛍 سرویس های من"}:
        await _send_services_list(message, seller_context, buyer_telegram_id=message.from_user.id)
    elif message.text in {"Renew", "افزایش اعتبار زمانی"}:
        await _send_services_list(message, seller_context, buyer_telegram_id=message.from_user.id)
    elif message.text in {"Wallet", "💸 شارژ حساب", "👤 پروفایل"}:
        await message.answer(
            await _wallet_text(seller_context, buyer_telegram_id=message.from_user.id),
            reply_markup=wallet_charge_menu(),
        )
        wallet_info = await seller_context.list_buyer_wallet(buyer_telegram_id=message.from_user.id)
        for transaction in wallet_info.transactions[:5]:
            await message.answer(
                _wallet_transaction_card_text(transaction),
                reply_markup=wallet_transaction_actions(transaction.id),
            )
    elif message.text in {"Support", "📮 پشتیبانی آنلاین"}:
        support_contact_line = await _support_contact_line(
            seller_context,
            buyer_telegram_id=message.from_user.id,
        )
        await message.answer(
            _guided_text(
                "📮 پشتیبانی آنلاین",
                "برای بررسی مشکل، تیکت ثبت کنید.",
                [support_contact_line, "برای تیکت جدید روی «🎟 ثبت تیکت» بزنید."],
            ),
            reply_markup=support_menu(),
        )
    elif message.text in {"Trial", "🎁 سرویس تستی (رایگان)"}:
        await trial(message, provisioning_service)
    elif message.text in {"Guides", "🔗 راهنمای اتصال"}:
        await message.answer(
            _guided_text(
                "🔗 راهنمای اتصال",
                "برای اتصال، لینک اشتراک را داخل برنامه‌هایی مثل Hiddify، V2RayNG، Streisand یا Nekobox وارد کنید.",
                [],
            ),
            reply_markup=seller_section_menu("guides"),
        )
    elif message.text in {"Pending Payments", "💳 پرداخت ها"}:
        await _send_admin_payments(message, seller_context)
    elif message.text in {"Provision Orders", "🧾 سفارش ها"}:
        await _send_admin_orders(message, seller_context)
    elif message.text in {"Wallet Charges", "💸 شارژ کیف پول"}:
        await _send_admin_wallet(message, seller_context)
    elif message.text in {"Customers", "👤 مدیریت کاربران"}:
        await _send_admin_customers(message, seller_context)
    elif message.text in {"Tickets", "📮 تیکت ها"}:
        await _send_admin_tickets(message, seller_context)
    elif message.text in {"Plans", "🛒 تعرفه خدمات"}:
        await _send_admin_plans(message, seller_context)
    elif message.text in {"Payment Method", "🪙 روش پرداخت"}:
        try:
            config = await seller_context.get_crypto_payment_config(admin_telegram_id=message.from_user.id)
        except PermissionError:
            await message.answer("شما دسترسی ادمین فروشنده ندارید.")
            return
        await message.answer(
            _crypto_payment_settings_text(config),
            reply_markup=admin_payment_settings_menu(has_crypto=config is not None),
        )
    elif message.text in {"Sales Report", "📊 گزارش فروش"}:
        try:
            report = await seller_context.sales_report(admin_telegram_id=message.from_user.id, days=1)
        except PermissionError:
            await message.answer("شما دسترسی ادمین فروشنده ندارید.")
            return
        await message.answer(_format_report("Sales Report - Today", report), reply_markup=seller_report_menu())
    elif message.text in {"Buyer Home", "📱 منوی اصلی"}:
        await start(message, seller_context)


@router.callback_query(F.data.startswith("s:"))
async def seller_menu_callback(
    callback: CallbackQuery,
    state: FSMContext,
    seller_context: SellerContextService,
    provisioning_service: ProvisioningService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    action = parse_callback(callback.data or "")
    if action.action == "home":
        await state.clear()
        profile = await seller_context.register_buyer(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            language_code=callback.from_user.language_code,
        )
        await callback.message.edit_text(
            _buyer_dashboard_text(
                seller_name=profile.seller_bot.name,
                reseller_name=profile.reseller.display_name,
            ),
            reply_markup=seller_buyer_menu(),
        )
    elif action.action == "plans":
        plans = await seller_context.list_plans(purpose=PlanPurpose.PURCHASE)
        await callback.message.edit_text(
            _plans_text_from_list(plans),
            reply_markup=plan_list_menu(plans),
        )
    elif action.action == "buy":
        if not action.value:
            await callback.answer("پلن مشخص نشده است.", show_alert=True)
            return
        plan = await _find_plan(seller_context, plan_id=action.value, purpose=PlanPurpose.PURCHASE)
        if plan is None:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        await state.clear()
        await state.update_data(
            buy_plan_id=plan.id,
            buy_coupon=None,
            buy_amount=float(plan.price),
            buy_requested_username=None,
        )
        await state.set_state(PurchaseCreateStates.username)
        await callback.message.edit_text(
            _purchase_username_text(plan),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="buy_cancel"),
        )
    elif action.action == "buy_coupon":
        data = await state.get_data()
        if not data.get("buy_plan_id"):
            await callback.answer("پیش نویس خرید پیدا نشد.", show_alert=True)
            return
        await state.set_state(PurchaseCreateStates.coupon)
        await callback.message.edit_text(
            "\n".join([title("کد تخفیف خرید"), "کد تخفیف این خرید را ارسال کنید."]),
            reply_markup=purchase_coupon_menu(),
        )
    elif action.action == "buy_no_coupon":
        await _show_purchase_confirm(callback, state, seller_context, coupon=None)
    elif action.action == "buy_create":
        data = await state.get_data()
        plan_id = data.get("buy_plan_id")
        if not plan_id:
            await callback.answer("پیش نویس خرید پیدا نشد.", show_alert=True)
            await state.clear()
            return
        try:
            wallet_purchase = await seller_context.purchase_with_wallet(
                buyer_telegram_id=callback.from_user.id,
                plan_id=str(plan_id),
                coupon_code=data.get("buy_coupon"),
                requested_username=data.get("buy_requested_username"),
            )
            provisioned = await provisioning_service.provision_buyer_order(
                buyer_telegram_id=callback.from_user.id,
                order_id=wallet_purchase.order.id,
            )
        except ValueError as exc:
            if str(exc) == "plan_not_found":
                await callback.answer("پلن پیدا نشد.", show_alert=True)
                await state.clear()
                return
            if str(exc) == "discount_not_found":
                await callback.answer("کد تخفیف پیدا نشد.", show_alert=True)
                return
            if str(exc) == "insufficient_wallet_balance":
                await state.clear()
                await callback.message.edit_text(
                    "\n".join(
                        [
                            title("💸 موجودی کافی نیست"),
                            "برای خرید این پلن ابتدا کیف پول خود را شارژ کنید.",
                            "",
                            "بعد از تایید شارژ، دوباره پلن را انتخاب کنید.",
                        ]
                    ),
                    reply_markup=wallet_charge_menu(),
                )
                return
            if str(exc) == "panel_assignment_not_found":
                await callback.answer("هیچ پنل مرزبان فعالی اختصاص داده نشده است.", show_alert=True)
                return
            raise
        except httpx.HTTPStatusError as exc:
            await callback.answer(_marzban_http_error_text(exc), show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("✅ خرید با موفقیت انجام شد"),
                    f"مبلغ کسر شده از کیف پول: {abs(float(wallet_purchase.transaction.amount)):,.0f} تومان",
                    "",
                    _service_created_text("سرویس شما ساخته شد.", provisioned.vpn_service),
                ]
            ),
            reply_markup=service_actions(provisioned.vpn_service.id),
        )
    elif action.action == "buy_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("خرید لغو شد"), "هیچ درخواست پرداختی ساخته نشد."]),
            reply_markup=seller_section_menu("plans"),
        )
    elif action.action == "services":
        await state.clear()
        services = await seller_context.list_buyer_services(buyer_telegram_id=callback.from_user.id)
        await callback.message.edit_text(
            _services_text_from_list(services),
            reply_markup=service_list_menu(services),
        )
    elif action.action == "service_detail":
        if not action.value:
            await callback.answer("سرویس مشخص نشده است.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=action.value,
        )
        if service is None:
            await callback.answer("سرویس پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            _service_detail_text(service),
            reply_markup=service_actions(service.id),
        )
    elif action.action == "service_qr":
        if not action.value:
            await callback.answer("سرویس مشخص نشده است.", show_alert=True)
            return
        services = await seller_context.list_buyer_services(buyer_telegram_id=callback.from_user.id)
        service = next((item for item in services if item.id == action.value), None)
        if service is None or not service.subscription_url:
            await callback.answer("لینک اشتراک در دسترس نیست.", show_alert=True)
            return
        qr_file = BufferedInputFile(
            make_qr_png_bytes(service.subscription_url),
            filename=f"{service.marzban_username}.png",
        )
        await callback.message.answer_photo(qr_file, caption=f"کد QR\nسرویس: {service.id}")
    elif action.action == "service_sub":
        if not action.value:
            await callback.answer("سرویس مشخص نشده است.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=action.value,
        )
        if service is None or not service.subscription_url:
            await callback.answer("لینک اشتراک در دسترس نیست.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("لینک اشتراک"),
                    f"سرویس: {service.marzban_username}",
                    f"کد سرویس: {service.id}",
                    "",
                    service.subscription_url,
                ]
            ),
            reply_markup=service_actions(service.id),
        )
    elif action.action == "service_guide":
        if not action.value:
            await callback.answer("سرویس مشخص نشده است.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=action.value,
        )
        if service is None:
            await callback.answer("سرویس پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            _service_guide_text(service.id),
            reply_markup=service_actions(service.id),
        )
    elif action.action == "renew":
        if not action.value:
            await callback.answer("سرویس مشخص نشده است.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=action.value,
        )
        if service is None:
            await callback.answer("سرویس پیدا نشد.", show_alert=True)
            return
        await state.clear()
        await state.update_data(renew_service_id=service.id)
        await state.set_state(RenewalCreateStates.plan)
        plans = await seller_context.list_plans(purpose=PlanPurpose.PURCHASE)
        await callback.message.edit_text(
            _renewal_text_from_list(plans, service_id=service.id),
            reply_markup=renewal_plan_list_menu(plans),
        )
    elif action.action == "extra_volume":
        if not action.value:
            await callback.answer("سرویس مشخص نشده است.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=action.value,
        )
        if service is None:
            await callback.answer("سرویس پیدا نشد.", show_alert=True)
            return
        await state.clear()
        await state.update_data(extra_service_id=service.id)
        await state.set_state(ExtraVolumeCreateStates.plan)
        await callback.message.edit_text(
            await _extra_volume_text(seller_context, service_id=service.id),
            reply_markup=service_actions(service.id),
        )
        plans = await seller_context.list_plans(purpose=PlanPurpose.EXTRA_VOLUME)
        for plan in plans[:8]:
            await callback.message.answer(
                _extra_volume_plan_card_text(plan),
                reply_markup=extra_volume_plan_button(plan.id),
            )
    elif action.action == "renew_services":
        await state.clear()
        services = await seller_context.list_buyer_services(buyer_telegram_id=callback.from_user.id)
        await callback.message.edit_text(
            _services_text_from_list(services),
            reply_markup=service_list_menu(services),
        )
    elif action.action == "renew_plan":
        if not action.value:
            await callback.answer("پلن مشخص نشده است.", show_alert=True)
            return
        data = await state.get_data()
        service_id = data.get("renew_service_id")
        if not service_id:
            await callback.answer("ابتدا یک سرویس انتخاب کنید.", show_alert=True)
            return
        plan = await _find_plan(seller_context, plan_id=action.value, purpose=PlanPurpose.PURCHASE)
        if plan is None:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=str(service_id),
        )
        if service is None:
            await callback.answer("سرویس پیدا نشد.", show_alert=True)
            await state.clear()
            return
        await state.update_data(renew_plan_id=plan.id, renew_coupon=None)
        await state.set_state(RenewalCreateStates.coupon)
        await callback.message.edit_text(
            _renewal_coupon_text(service, plan),
            reply_markup=renewal_coupon_menu(),
        )
    elif action.action == "extra_plan":
        if not action.value:
            await callback.answer("پلن مشخص نشده است.", show_alert=True)
            return
        data = await state.get_data()
        service_id = data.get("extra_service_id")
        if not service_id:
            await callback.answer("ابتدا یک سرویس انتخاب کنید.", show_alert=True)
            return
        plan = await _find_plan(seller_context, plan_id=action.value, purpose=PlanPurpose.EXTRA_VOLUME)
        if plan is None:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        service = await _find_buyer_service(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            service_id=str(service_id),
        )
        if service is None:
            await callback.answer("سرویس پیدا نشد.", show_alert=True)
            await state.clear()
            return
        await state.update_data(extra_plan_id=plan.id, extra_coupon=None)
        await state.set_state(ExtraVolumeCreateStates.coupon)
        await callback.message.edit_text(
            _extra_volume_coupon_text(service, plan),
            reply_markup=extra_volume_coupon_menu(),
        )
    elif action.action == "renew_coupon":
        data = await state.get_data()
        if not data.get("renew_service_id") or not data.get("renew_plan_id"):
            await callback.answer("پیش نویس تمدید پیدا نشد.", show_alert=True)
            return
        await state.set_state(RenewalCreateStates.coupon)
        await callback.message.edit_text(
            "\n".join([title("کد تخفیف تمدید"), "کد تخفیف تمدید را ارسال کنید."]),
            reply_markup=renewal_coupon_menu(),
        )
    elif action.action == "renew_no_coupon":
        await _show_renewal_confirm(callback, state, seller_context, coupon=None)
    elif action.action == "extra_coupon":
        data = await state.get_data()
        if not data.get("extra_service_id") or not data.get("extra_plan_id"):
            await callback.answer("پیش نویس خرید حجم اضافه پیدا نشد.", show_alert=True)
            return
        await state.set_state(ExtraVolumeCreateStates.coupon)
        await callback.message.edit_text(
            "\n".join([title("کد تخفیف حجم اضافه"), "کد تخفیف خرید حجم اضافه را ارسال کنید."]),
            reply_markup=extra_volume_coupon_menu(),
        )
    elif action.action == "extra_no_coupon":
        await _show_extra_volume_confirm(callback, state, seller_context, coupon=None)
    elif action.action == "renew_create":
        data = await state.get_data()
        service_id = data.get("renew_service_id")
        plan_id = data.get("renew_plan_id")
        if not service_id or not plan_id:
            await callback.answer("پیش نویس تمدید پیدا نشد.", show_alert=True)
            await state.clear()
            return
        try:
            payment_request = await seller_context.request_renewal_payment(
                buyer_telegram_id=callback.from_user.id,
                service_id=str(service_id),
                plan_id=str(plan_id),
                coupon_code=data.get("renew_coupon"),
            )
        except ValueError as exc:
            if str(exc) == "service_not_found":
                await callback.answer("سرویس پیدا نشد.", show_alert=True)
                await state.clear()
                return
            if str(exc) == "plan_not_found":
                await callback.answer("پلن پیدا نشد.", show_alert=True)
                return
            if str(exc) == "discount_not_found":
                await callback.answer("کد تخفیف پیدا نشد.", show_alert=True)
                return
            raise
        await state.clear()
        await callback.message.edit_text(
            _payment_request_text(payment_request),
            reply_markup=payment_request_actions(payment_request.order.id),
        )
    elif action.action == "extra_create":
        data = await state.get_data()
        service_id = data.get("extra_service_id")
        plan_id = data.get("extra_plan_id")
        if not service_id or not plan_id:
            await callback.answer("پیش نویس خرید حجم اضافه پیدا نشد.", show_alert=True)
            await state.clear()
            return
        try:
            payment_request = await seller_context.request_extra_volume_payment(
                buyer_telegram_id=callback.from_user.id,
                service_id=str(service_id),
                plan_id=str(plan_id),
                coupon_code=data.get("extra_coupon"),
            )
        except ValueError as exc:
            if str(exc) == "service_not_found":
                await callback.answer("سرویس پیدا نشد.", show_alert=True)
                await state.clear()
                return
            if str(exc) == "plan_not_found":
                await callback.answer("پلن پیدا نشد.", show_alert=True)
                return
            if str(exc) == "discount_not_found":
                await callback.answer("کد تخفیف پیدا نشد.", show_alert=True)
                return
            raise
        await state.clear()
        await callback.message.edit_text(
            _payment_request_text(payment_request),
            reply_markup=payment_request_actions(payment_request.order.id),
        )
    elif action.action == "renew_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("تمدید لغو شد"), "هیچ درخواست پرداخت تمدیدی ساخته نشد."]),
            reply_markup=seller_section_menu("services"),
        )
    elif action.action == "extra_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("خرید حجم اضافه لغو شد"), "هیچ درخواست پرداخت حجم اضافه ساخته نشد."]),
            reply_markup=seller_section_menu("services"),
        )
    elif action.action == "wallet":
        await state.clear()
        await callback.message.edit_text(
            await _wallet_text(seller_context, buyer_telegram_id=callback.from_user.id),
            reply_markup=wallet_charge_menu(),
        )
        wallet_info = await seller_context.list_buyer_wallet(buyer_telegram_id=callback.from_user.id)
        for transaction in wallet_info.transactions[:5]:
            await callback.message.answer(
                _wallet_transaction_card_text(transaction),
                reply_markup=wallet_transaction_actions(transaction.id),
            )
    elif action.action == "wallet_tx":
        if not action.value:
            await callback.answer("تراکنش مشخص نشده است.", show_alert=True)
            return
        try:
            transaction = await seller_context.get_buyer_wallet_transaction(
                buyer_telegram_id=callback.from_user.id,
                transaction_id=action.value,
            )
        except ValueError:
            await callback.answer("تراکنش پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            _wallet_transaction_detail_text(transaction),
            reply_markup=wallet_transaction_actions(transaction.id),
        )
    elif action.action == "order_status":
        if not action.value:
            await callback.answer("سفارش مشخص نشده است.", show_alert=True)
            return
        try:
            order_status = await seller_context.get_buyer_order_status(
                buyer_telegram_id=callback.from_user.id,
                order_id=action.value,
            )
        except ValueError:
            await callback.answer("سفارش پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            _buyer_order_status_text(order_status),
            reply_markup=payment_request_actions(order_status.order.id),
        )
    elif action.action == "receipt_upload":
        if not action.value:
            await callback.answer("سفارش مشخص نشده است.", show_alert=True)
            return
        await state.clear()
        await state.update_data(receipt_order_id=action.value)
        await state.set_state(ReceiptUploadStates.photo)
        await callback.message.edit_text(
            _receipt_upload_request_text(action.value),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="home"),
        )
    elif action.action == "wallet_receipt_upload":
        if not action.value:
            await callback.answer("درخواست شارژ کیف پول مشخص نشده است.", show_alert=True)
            return
        await state.clear()
        await state.update_data(receipt_transaction_id=action.value)
        await state.set_state(ReceiptUploadStates.photo)
        await callback.message.edit_text(
            _wallet_receipt_upload_request_text(action.value),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="wallet"),
        )
    elif action.action == "wallet_add":
        if not action.value:
            await callback.answer("مبلغ مشخص نشده است.", show_alert=True)
            return
        try:
            amount = float(action.value)
        except ValueError:
            await callback.answer("مبلغ نامعتبر است.", show_alert=True)
            return
        await state.update_data(wallet_amount=amount)
        await state.set_state(WalletChargeStates.confirm)
        await callback.message.edit_text(
            _wallet_charge_confirm_text(amount),
            reply_markup=confirm_keyboard(
                scope="s",
                confirm_action="wallet_create",
                cancel_action="wallet_cancel",
            ),
        )
    elif action.action == "wallet_custom":
        await state.clear()
        await state.set_state(WalletChargeStates.amount)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("شارژ دلخواه کیف پول"),
                    "مبلغ دلخواه برای شارژ را بفرستید.",
                    "",
                    "Example: 250000",
                ]
            ),
            reply_markup=wallet_charge_menu(),
        )
    elif action.action == "wallet_create":
        data = await state.get_data()
        amount = data.get("wallet_amount")
        if amount is None:
            await callback.answer("پیش نویس شارژ کیف پول پیدا نشد.", show_alert=True)
            await state.clear()
            return
        try:
            charge = await seller_context.request_wallet_charge(
                buyer_telegram_id=callback.from_user.id,
                amount=float(amount),
            )
        except ValueError:
            await callback.answer("شارژ کیف پول نامعتبر است.", show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            _wallet_charge_request_text(charge),
            reply_markup=wallet_charge_request_actions(charge.transaction.id),
        )
    elif action.action == "wallet_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("شارژ کیف پول لغو شد"), "هیچ درخواست شارژی ساخته نشد."]),
            reply_markup=wallet_charge_menu(),
        )
    elif action.action == "trial":
        try:
            service = await provisioning_service.provision_trial(
                buyer_telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                language_code=callback.from_user.language_code,
            )
        except ValueError as exc:
            await callback.message.edit_text(
                _trial_error_text(str(exc)),
                reply_markup=seller_section_menu("trial"),
            )
        else:
            await callback.message.edit_text(
                _service_created_text("سرویس تستی VPN ساخته شد.", service),
                reply_markup=seller_section_menu("trial"),
            )
    elif action.action == "support":
        support_contact_line = await _support_contact_line(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
        )
        await callback.message.edit_text(
            _guided_text(
                "📮 پشتیبانی آنلاین",
                "برای بررسی مشکل، تیکت ثبت کنید.",
                [support_contact_line, "برای تیکت جدید روی «🎟 ثبت تیکت» بزنید."],
            ),
            reply_markup=support_menu(),
        )
    elif action.action == "tickets":
        await callback.message.edit_text(
            await _buyer_tickets_text(seller_context, buyer_telegram_id=callback.from_user.id),
            reply_markup=support_menu(),
        )
        for ticket_item in (await seller_context.list_my_tickets(buyer_telegram_id=callback.from_user.id))[:5]:
            await callback.message.answer(
                _ticket_card_text(ticket_item),
                reply_markup=buyer_ticket_actions(ticket_item.id),
            )
    elif action.action == "ticket_detail":
        if not action.value:
            await callback.answer("تیکت مشخص نشده است.", show_alert=True)
            return
        try:
            thread = await seller_context.get_buyer_ticket_thread(
                buyer_telegram_id=callback.from_user.id,
                ticket_id=action.value,
            )
        except ValueError:
            await callback.answer("تیکت پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            _ticket_thread_text(thread),
            reply_markup=buyer_ticket_actions(thread.ticket.id),
        )
    elif action.action == "ticket_reply":
        if not action.value:
            await callback.answer("تیکت مشخص نشده است.", show_alert=True)
            return
        try:
            thread = await seller_context.get_buyer_ticket_thread(
                buyer_telegram_id=callback.from_user.id,
                ticket_id=action.value,
            )
        except ValueError:
            await callback.answer("تیکت پیدا نشد.", show_alert=True)
            return
        await state.clear()
        await state.update_data(reply_ticket_id=thread.ticket.id)
        await state.set_state(TicketReplyStates.buyer_body)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("پاسخ به تیکت"),
                    f"کد تیکت: {thread.ticket.id}",
                    f"موضوع: {thread.ticket.subject}",
                    "",
                    "پیام پاسخ خود را بفرستید.",
                ]
            ),
            reply_markup=buyer_ticket_actions(thread.ticket.id),
        )
    elif action.action == "ticket_open":
        await state.clear()
        await state.set_state(TicketCreateStates.subject)
        support_contact_line = await _support_contact_line(
            seller_context,
            buyer_telegram_id=callback.from_user.id,
        )
        await callback.message.edit_text(
            "\n".join(
                [
                    title("ثبت تیکت"),
                    support_contact_line,
                    "",
                    "موضوع تیکت را بفرستید.",
                    "",
                    "Example: Cannot connect on Android",
                ]
            ),
            reply_markup=support_menu(),
        )
    elif action.action == "ticket_create":
        data = await state.get_data()
        subject = str(data.get("ticket_subject") or "").strip()
        body = str(data.get("ticket_body") or "").strip()
        if not subject or not body:
            await callback.answer("پیش نویس تیکت کامل نیست.", show_alert=True)
            await state.clear()
            return
        try:
            thread = await seller_context.open_ticket(
                buyer_telegram_id=callback.from_user.id,
                subject=subject,
                body=body,
            )
        except ValueError as exc:
            await callback.answer(f"Could not open ticket: {exc}", show_alert=True)
            return
        await state.clear()
        await _notify_support_about_ticket(
            callback.message,
            seller_context,
            buyer_telegram_id=callback.from_user.id,
            header="تیکت جدید",
            ticket_id=thread.ticket.id,
            subject=thread.ticket.subject,
            body=body,
        )
        await callback.message.edit_text(
            "\n".join(
                [
                    title("تیکت ثبت شد"),
                    f"کد تیکت: {thread.ticket.id}",
                    f"موضوع: {thread.ticket.subject}",
                    f"وضعیت: {status_label(thread.ticket.status)}",
                ]
            ),
            reply_markup=support_menu(),
        )
    elif action.action == "ticket_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("تیکت لغو شد"), "هیچ تیکتی ساخته نشد."]),
            reply_markup=support_menu(),
        )
    elif action.action == "guides":
        await callback.message.edit_text(
            _guided_text(
                "Connection Guides",
                "Use your subscription link in V2RayNG, Streisand, Hiddify, or Nekobox.",
                [],
            ),
            reply_markup=seller_section_menu("guides"),
        )
    elif action.action == "admin":
        await _show_admin_dashboard(callback, seller_context)
    elif action.action == "admin_payments":
        await _show_admin_payments(callback, seller_context)
    elif action.action == "admin_payment_settings":
        await _show_admin_payment_settings(callback, seller_context)
    elif action.action == "admin_crypto_payment_setup":
        try:
            await seller_context.ensure_reseller_admin(admin_telegram_id=callback.from_user.id)
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        await state.clear()
        await state.set_state(CryptoPaymentSetupStates.currency)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("ساخت روش پرداخت ارز دیجیتال"),
                    "نام ارز را بفرستید.",
                    "",
                    "مثال: USDT",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_payment_settings"),
        )
    elif action.action == "admin_crypto_payment_save":
        data = await state.get_data()
        spec = data.get("crypto_payment")
        if not isinstance(spec, dict):
            await state.clear()
            await callback.answer("پیش نویس پرداخت منقضی شد. دوباره شروع کنید.", show_alert=True)
            await _show_admin_payment_settings(callback, seller_context)
            return
        try:
            config = await seller_context.set_crypto_payment_config(
                admin_telegram_id=callback.from_user.id,
                currency=str(spec["currency"]),
                network=str(spec["network"]),
                wallet_address=str(spec["wallet_address"]),
                note=str(spec.get("note") or "").strip() or None,
            )
        except PermissionError:
            await state.clear()
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await state.clear()
            await callback.answer("ذخیره تنظیمات پرداخت ارز دیجیتال ممکن نشد.", show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            _crypto_payment_settings_text(config),
            reply_markup=admin_payment_settings_menu(has_crypto=True),
        )
    elif action.action == "admin_orders":
        await _show_admin_orders(callback, seller_context)
    elif action.action == "admin_wallet":
        await _show_admin_wallet(callback, seller_context)
    elif action.action == "admin_customers":
        await _show_admin_customers(callback, seller_context)
    elif action.action == "admin_customer_search":
        await state.clear()
        await state.set_state(AdminCustomerSearchStates.query)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("جستجوی کاربر"),
                    "Telegram ID، @username، نام کاربر یا نام VPN را بفرستید.",
                ]
            ),
            reply_markup=admin_customers_menu(),
        )
    elif action.action == "admin_customer_detail":
        if not action.value:
            await callback.answer("کاربر مشخص نشده است.", show_alert=True)
            return
        try:
            detail = await seller_context.get_customer_detail(
                admin_telegram_id=callback.from_user.id,
                buyer_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("کاربر پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            _admin_customer_detail_text(detail),
            reply_markup=admin_customer_detail_actions(detail.buyer.id),
        )
    elif action.action in {"admin_customer_message", "admin_customer_wallet", "admin_customer_block"}:
        await callback.answer("این عملیات کاربر در مرحله بعدی اضافه می‌شود.", show_alert=True)
    elif action.action == "admin_tickets":
        await _show_admin_tickets(callback, seller_context)
    elif action.action == "admin_support_settings":
        await _show_admin_support_settings(callback, seller_context)
    elif action.action == "admin_support_set":
        try:
            await seller_context.ensure_reseller_admin(admin_telegram_id=callback.from_user.id)
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        await state.clear()
        await state.set_state(SupportSettingsStates.telegram_id)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("تنظیم پشتیبان"),
                    "یکی از این موارد را بفرستید:",
                    "",
                    "Telegram ID عددی مثل 252486544",
                    "یوزرنیم مثل @support_user",
                    "یا یک پیام فوروارد شده از پشتیبان",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_support_settings"),
        )
    elif action.action == "admin_support_delete_confirm":
        await callback.message.edit_text(
            "\n".join(
                [
                    title("حذف پشتیبان"),
                    "بعد از حذف، تیکت‌ها فقط داخل ربات ذخیره می‌شوند و پیام مستقیم برای پشتیبان ارسال نمی‌شود.",
                ]
            ),
            reply_markup=confirm_keyboard(
                scope="s",
                confirm_action="admin_support_delete",
                cancel_action="admin_support_settings",
            ),
        )
    elif action.action == "admin_support_delete":
        try:
            settings = await seller_context.delete_support_telegram_id(admin_telegram_id=callback.from_user.id)
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        await callback.message.edit_text(
            _support_settings_text(settings),
            reply_markup=admin_support_settings_menu(has_support=False),
        )
    elif action.action == "admin_plans":
        await _show_admin_plans(callback, seller_context)
    elif action.action == "admin_plan_detail":
        if not action.value:
            await callback.answer("پلن مشخص نشده است.", show_alert=True)
            return
        try:
            plans = await seller_context.list_admin_plans(admin_telegram_id=callback.from_user.id)
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        plan = _find_admin_plan(plans, plan_id=action.value)
        if plan is None:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            _admin_plan_card_text(plan),
            reply_markup=admin_plan_actions(plan.id) if plan.reseller_id else admin_plans_menu(),
        )
    elif action.action == "admin_plan_add":
        try:
            await seller_context.ensure_reseller_admin(admin_telegram_id=callback.from_user.id)
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        await state.clear()
        await state.set_state(AdminPlanCreateStates.name)
        await state.update_data(admin_plan_mode="create")
        await callback.message.edit_text(
            "\n".join(
                [
                    title("افزودن پلن فروش"),
                    "اسم پلن را بفرستید.",
                    "",
                    "این همان متنی است که کاربر روی دکمه خرید می‌بیند.",
                    "مثال: پلن اقتصادی 30 روزه",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
        )
    elif action.action == "admin_plan_edit":
        if not action.value:
            await callback.answer("پلن مشخص نشده است.", show_alert=True)
            return
        try:
            plan = await seller_context.get_admin_plan(
                admin_telegram_id=callback.from_user.id,
                plan_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        await state.clear()
        await state.set_state(AdminPlanCreateStates.name)
        await state.update_data(admin_plan_mode="edit", admin_plan_id=plan.id)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("ویرایش پلن فروش"),
                    "اسم جدید پلن را بفرستید.",
                    "",
                    f"اسم فعلی: {plan.name}",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
        )
    elif action.action == "admin_plan_create":
        data = await state.get_data()
        spec = data.get("admin_plan")
        if not isinstance(spec, dict):
            await state.clear()
            await callback.answer("پیش نویس پلن منقضی شد. دوباره شروع کنید.", show_alert=True)
            await _show_admin_plans(callback, seller_context)
            return
        try:
            if data.get("admin_plan_mode") == "edit":
                plan_id = data.get("admin_plan_id")
                if not plan_id:
                    raise ValueError("plan_not_found")
                plan = await seller_context.update_admin_plan(
                    admin_telegram_id=callback.from_user.id,
                    plan_id=str(plan_id),
                    name=str(spec["name"]),
                    price=float(spec["price"]),
                    duration_days=int(spec["duration_days"]),
                    data_limit_gb=int(spec["data_limit_gb"]),
                )
            else:
                plan = await seller_context.create_admin_plan(
                    admin_telegram_id=callback.from_user.id,
                    name=str(spec["name"]),
                    price=float(spec["price"]),
                    duration_days=int(spec["duration_days"]),
                    data_limit_gb=spec["data_limit_gb"],
                    purpose=PlanPurpose.PURCHASE,
                )
        except PermissionError:
            await state.clear()
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await state.clear()
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        await state.clear()
        await callback.message.edit_text(
            _admin_plan_saved_text(plan, edited=data.get("admin_plan_mode") == "edit"),
            reply_markup=admin_plans_menu(),
        )
    elif action.action == "admin_plan_delete_confirm":
        if not action.value:
            await callback.answer("پلن مشخص نشده است.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("حذف پلن"),
                    "این پلن از لیست خرید کاربران حذف می‌شود.",
                    "",
                    "سفارش‌ها و گزارش‌های قبلی حفظ می‌شوند.",
                ]
            ),
            reply_markup=confirm_keyboard(
                scope="s",
                confirm_action="admin_plan_delete",
                cancel_action="admin_plans",
                value=action.value,
            ),
        )
    elif action.action == "admin_plan_delete":
        if not action.value:
            await callback.answer("پلن مشخص نشده است.", show_alert=True)
            return
        try:
            plan = await seller_context.deactivate_admin_plan(
                admin_telegram_id=callback.from_user.id,
                plan_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join([title("پلن حذف شد"), f"نام: {plan.name}", "", "این پلن دیگر برای کاربران نمایش داده نمی‌شود."]),
            reply_markup=admin_plans_menu(),
        )
    elif action.action == "admin_ticket_detail":
        if not action.value:
            await callback.answer("تیکت مشخص نشده است.", show_alert=True)
            return
        try:
            thread = await seller_context.get_admin_ticket_thread(
                admin_telegram_id=callback.from_user.id,
                ticket_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("تیکت پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            _ticket_thread_text(thread),
            reply_markup=admin_ticket_actions(thread.ticket.id),
        )
    elif action.action == "admin_ticket_reply":
        if not action.value:
            await callback.answer("تیکت مشخص نشده است.", show_alert=True)
            return
        try:
            thread = await seller_context.get_admin_ticket_thread(
                admin_telegram_id=callback.from_user.id,
                ticket_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("تیکت پیدا نشد.", show_alert=True)
            return
        await state.clear()
        await state.update_data(reply_ticket_id=thread.ticket.id)
        await state.set_state(TicketReplyStates.admin_body)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("پاسخ ادمین"),
                    f"کد تیکت: {thread.ticket.id}",
                    f"موضوع: {thread.ticket.subject}",
                    "",
                    "پاسخ این کاربر را بفرستید.",
                ]
            ),
            reply_markup=admin_ticket_actions(thread.ticket.id),
        )
    elif action.action == "admin_report":
        days = 1
        if action.value:
            if not action.value.isdigit():
                await callback.answer("بازه گزارش نامعتبر است.", show_alert=True)
                return
            days = int(action.value)
        if days not in {1, 7, 30}:
            await callback.answer("بازه گزارش نامعتبر است.", show_alert=True)
            return
        try:
            report = await seller_context.sales_report(admin_telegram_id=callback.from_user.id, days=days)
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        label = "Today" if days == 1 else f"Last {days} Days"
        await callback.message.edit_text(
            _format_report(f"Sales Report - {label}", report),
            reply_markup=seller_report_menu(),
        )
    elif action.action == "admin_report_custom":
        await state.clear()
        await state.set_state(SellerReportCustomStates.days)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("گزارش فروش دلخواه"),
                    "تعداد روزهای گزارش را بفرستید.",
                    "",
                    "Example: 14",
                ]
            ),
            reply_markup=seller_report_menu(),
        )
    elif action.action == "admin_broadcast":
        await state.clear()
        await state.set_state(SellerBroadcastCreateStates.title)
        await callback.message.edit_text(
            "\n".join(
                [
                    title("ساخت پیام همگانی"),
                    "عنوان پیام همگانی برای کاربران خود را بفرستید.",
                    "",
                    "Example: New plans are available",
                ]
            ),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "broadcast_create":
        data = await state.get_data()
        broadcast_title = str(data.get("seller_broadcast_title") or "").strip()
        broadcast_body = str(data.get("seller_broadcast_body") or "").strip()
        if not broadcast_title or not broadcast_body:
            await callback.answer("پیش نویس پیام همگانی کامل نیست.", show_alert=True)
            await state.clear()
            return
        try:
            draft = await seller_context.create_broadcast(
                admin_telegram_id=callback.from_user.id,
                title=broadcast_title,
                body=broadcast_body,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            await state.clear()
            return
        await state.clear()
        await callback.message.edit_text(
            "\n".join(
                [
                    title("پیش نویس پیام همگانی ساخته شد"),
                    f"ID: {draft.broadcast.id}",
                    f"Targets: {len(draft.recipients)}",
                    "",
                    "Use /send_broadcast with this ID when you are ready to deliver it.",
                ]
            ),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "broadcast_cancel":
        await state.clear()
        await callback.message.edit_text(
            "\n".join([title("پیام همگانی لغو شد"), "هیچ پیش نویسی ساخته نشد."]),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "pay_detail":
        if not action.value:
            await callback.answer("پرداخت مشخص نشده است.", show_alert=True)
            return
        try:
            pending = await seller_context.get_pending_payment(
                admin_telegram_id=callback.from_user.id,
                payment_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("پرداخت در انتظار پیدا نشد.", show_alert=True)
            return
        await _edit_or_answer_callback(
            callback,
            _pending_payment_detail_text(pending),
            reply_markup=admin_payment_actions(pending.payment.id),
        )
    elif action.action == "pay_ok":
        if not action.value:
            await callback.answer("پرداخت مشخص نشده است.", show_alert=True)
            return
        try:
            approved = await seller_context.approve_payment(
                admin_telegram_id=callback.from_user.id,
                payment_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("پرداخت در انتظار پیدا نشد.", show_alert=True)
            return
        is_renewal = approved.order.order_type == OrderType.RENEWAL.value
        is_extra_volume = approved.order.order_type == OrderType.EXTRA_VOLUME.value
        await _edit_or_answer_callback(
            callback,
            "\n".join(
                [
                    title("پرداخت تایید شد"),
                    f"کد پرداخت: {approved.payment.id}",
                    f"کد سفارش: {approved.order.id}",
                    f"وضعیت سفارش: {status_label(approved.order.status)}",
                ]
            ),
            reply_markup=admin_order_actions(
                approved.order.id,
                renewal=is_renewal,
                extra_volume=is_extra_volume,
            ),
        )
    elif action.action == "pay_reject_confirm":
        if not action.value:
            await callback.answer("پرداخت مشخص نشده است.", show_alert=True)
            return
        await _edit_or_answer_callback(
            callback,
            "\n".join(
                [
                    title("تایید رد پرداخت"),
                    f"کد پرداخت: {action.value}",
                    "",
                    "رد کردن پرداخت، سفارش را لغو می‌کند و دیگر نمی‌توان از این پرداخت سرویس ساخت.",
                ]
            ),
            reply_markup=confirm_keyboard(
                scope="s",
                confirm_action="pay_reject",
                cancel_action="admin_payments",
                value=action.value,
            ),
        )
    elif action.action == "pay_reject":
        if not action.value:
            await callback.answer("پرداخت مشخص نشده است.", show_alert=True)
            return
        try:
            rejected = await seller_context.reject_payment(
                admin_telegram_id=callback.from_user.id,
                payment_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("پرداخت در انتظار پیدا نشد.", show_alert=True)
            return
        await _edit_or_answer_callback(
            callback,
            "\n".join(
                [
                    title("پرداخت رد شد"),
                    f"کد پرداخت: {rejected.payment.id}",
                    f"وضعیت پرداخت: {status_label(rejected.payment.status)}",
                    f"کد سفارش: {rejected.order.id}",
                    f"Order status: {status_label(rejected.order.status)}",
                ]
            ),
            reply_markup=seller_admin_menu(),
        )
    elif action.action in {"confirm_provision", "confirm_renewal", "confirm_extra_volume"}:
        if not action.value:
            await callback.answer("سفارش مشخص نشده است.", show_alert=True)
            return
        is_renewal = action.action == "confirm_renewal"
        is_extra_volume = action.action == "confirm_extra_volume"
        if is_extra_volume:
            confirm_action = "apply_extra_volume"
            action_label = "Apply extra volume"
        elif is_renewal:
            confirm_action = "apply_renewal"
            action_label = "Apply renewal"
        else:
            confirm_action = "provision_order"
            action_label = "Provision VPN service"
        await callback.message.edit_text(
            "\n".join(
                [
                    title("تایید ساخت سرویس"),
                    f"کد سفارش: {action.value}",
                    f"Action: {action_label}",
                    "",
                    "Confirm only after checking the approved payment.",
                ]
            ),
            reply_markup=confirm_keyboard(
                scope="s",
                confirm_action=confirm_action,
                cancel_action="admin_payments",
                value=action.value,
            ),
        )
    elif action.action == "provision_order":
        if not action.value:
            await callback.answer("سفارش مشخص نشده است.", show_alert=True)
            return
        try:
            provisioned = await provisioning_service.provision_order(
                admin_telegram_id=callback.from_user.id,
                order_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError as exc:
            if str(exc) == "order_already_completed_without_service_link":
                await callback.answer(
                    "سفارش تکمیل شده اما لینک سرویس آن ثبت نشده است. از سوپر ادمین بخواهید آن را اصلاح کند.",
                    show_alert=True,
                )
                return
            await callback.answer(f"Could not provision: {exc}", show_alert=True)
            return
        except httpx.HTTPStatusError as exc:
            await callback.answer(_marzban_http_error_text(exc), show_alert=True)
            return
        await callback.message.edit_text(
            _service_created_text("VPN service provisioned.", provisioned.vpn_service),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "apply_renewal":
        if not action.value:
            await callback.answer("سفارش مشخص نشده است.", show_alert=True)
            return
        try:
            renewed = await provisioning_service.apply_renewal(
                admin_telegram_id=callback.from_user.id,
                order_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError as exc:
            await callback.answer(f"Could not renew: {exc}", show_alert=True)
            return
        except httpx.HTTPStatusError as exc:
            await callback.answer(_marzban_http_error_text(exc), show_alert=True)
            return
        await callback.message.edit_text(
            _service_created_text("VPN service renewed.", renewed.vpn_service),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "apply_extra_volume":
        if not action.value:
            await callback.answer("سفارش مشخص نشده است.", show_alert=True)
            return
        try:
            applied = await provisioning_service.apply_extra_volume(
                admin_telegram_id=callback.from_user.id,
                order_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError as exc:
            await callback.answer(f"Could not add volume: {exc}", show_alert=True)
            return
        except httpx.HTTPStatusError as exc:
            await callback.answer(_marzban_http_error_text(exc), show_alert=True)
            return
        await callback.message.edit_text(
            _service_created_text("Extra volume applied.", applied.vpn_service),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "wallet_ok":
        if not action.value:
            await callback.answer("تراکنش مشخص نشده است.", show_alert=True)
            return
        try:
            approved = await seller_context.approve_wallet_charge(
                admin_telegram_id=callback.from_user.id,
                transaction_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("این شارژ قبلاً تایید شده یا دیگر pending نیست.", show_alert=True)
            return
        await _edit_or_answer_callback(
            callback,
            "\n".join(
                [
                    title("شارژ کیف پول تایید شد"),
                    f"Transaction ID: {approved.transaction.id}",
                    f"مبلغ: {approved.transaction.amount:,.0f}",
                ]
            ),
            reply_markup=seller_admin_menu(),
        )
    elif action.action == "ticket_close":
        if not action.value:
            await callback.answer("تیکت مشخص نشده است.", show_alert=True)
            return
        try:
            ticket_item = await seller_context.close_ticket(
                admin_telegram_id=callback.from_user.id,
                ticket_id=action.value,
            )
        except PermissionError:
            await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
            return
        except ValueError:
            await callback.answer("تیکت پیدا نشد.", show_alert=True)
            return
        await callback.message.edit_text(
            "\n".join(
                [
                    title("تیکت بسته شد"),
                    f"کد تیکت: {ticket_item.id}",
                    f"موضوع: {ticket_item.subject}",
                    f"وضعیت: {status_label(ticket_item.status)}",
                ]
            ),
            reply_markup=seller_admin_menu(),
        )
    await callback.answer()


@router.message(CryptoPaymentSetupStates.currency)
async def crypto_payment_currency(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    currency = message.text.strip()
    if not currency or currency.startswith("/"):
        await message.answer(
            "\n".join([title("نام ارز نامعتبر است"), "فقط نام ارز را بفرستید.", "", "مثال: USDT"]),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_payment_settings"),
        )
        return
    await state.update_data(crypto_payment={"currency": currency[:32]})
    await state.set_state(CryptoPaymentSetupStates.network)
    await message.answer(
        "\n".join(
            [
                title("شبکه پرداخت"),
                "نام شبکه را بفرستید.",
                "",
                "مثال: TRC20 یا BEP20",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_payment_settings"),
    )


@router.message(CryptoPaymentSetupStates.network)
async def crypto_payment_network(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    network = message.text.strip()
    if not network or network.startswith("/"):
        await message.answer(
            "\n".join([title("شبکه نامعتبر است"), "فقط نام شبکه را بفرستید.", "", "مثال: TRC20"]),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_payment_settings"),
        )
        return
    data = await state.get_data()
    spec = dict(data.get("crypto_payment") or {})
    spec["network"] = network[:32]
    await state.update_data(crypto_payment=spec)
    await state.set_state(CryptoPaymentSetupStates.wallet_address)
    await message.answer(
        "\n".join(
            [
                title("آدرس ولت"),
                "آدرس کامل ولت را بفرستید.",
                "",
                "این متن دقیقاً برای خریدار نمایش داده می‌شود.",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_payment_settings"),
    )


@router.message(CryptoPaymentSetupStates.wallet_address)
async def crypto_payment_wallet_address(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    wallet_address = message.text.strip()
    if len(wallet_address) < 8 or wallet_address.startswith("/"):
        await message.answer(
            "\n".join([title("آدرس ولت نامعتبر است"), "آدرس کامل ولت را دوباره بفرستید."]),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_payment_settings"),
        )
        return
    data = await state.get_data()
    spec = dict(data.get("crypto_payment") or {})
    spec["wallet_address"] = wallet_address[:256]
    await state.update_data(crypto_payment=spec)
    await state.set_state(CryptoPaymentSetupStates.note)
    await message.answer(
        "\n".join(
            [
                title("توضیح پرداخت"),
                "اگر نکته‌ای لازم است بفرستید.",
                "",
                "مثال: فقط روی شبکه TRC20 پرداخت شود.",
                "اگر توضیح لازم نیست، فقط - بفرستید.",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_payment_settings"),
    )


@router.message(CryptoPaymentSetupStates.note)
async def crypto_payment_note(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    note = message.text.strip()
    data = await state.get_data()
    spec = dict(data.get("crypto_payment") or {})
    spec["note"] = None if note in {"", "-"} else note[:512]
    await state.update_data(crypto_payment=spec)
    await state.set_state(CryptoPaymentSetupStates.confirm)
    await message.answer(
        _crypto_payment_confirm_text(spec),
        reply_markup=confirm_keyboard(
            scope="s",
            confirm_action="admin_crypto_payment_save",
            cancel_action="admin_payment_settings",
        ),
    )


@router.message(CryptoPaymentSetupStates.confirm)
async def crypto_payment_confirm_text_input(message: Message) -> None:
    await message.answer(
        "برای ذخیره روش پرداخت از دکمه تایید استفاده کنید.",
        reply_markup=confirm_keyboard(
            scope="s",
            confirm_action="admin_crypto_payment_save",
            cancel_action="admin_payment_settings",
        ),
    )


@router.message(SupportSettingsStates.telegram_id)
async def support_settings_telegram_id(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    support_contact = _extract_support_contact_from_message(message)
    if support_contact is None:
        await message.answer(
            "\n".join(
                [
                    title("پشتیبان نامعتبر است"),
                    "یکی از این موارد را بفرستید:",
                    "",
                    "Telegram ID عددی مثل 252486544",
                    "یوزرنیم مثل @support_user",
                    "یا پیام فوروارد شده از پشتیبان",
                    "",
                    "اگر فوروارد جواب نداد، یعنی حساب کاربر فوروارد را مخفی کرده است.",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_support_settings"),
        )
        return
    try:
        settings = await seller_context.set_support_contact(
            admin_telegram_id=message.from_user.id,
            support_contact=support_contact,
        )
    except PermissionError:
        await state.clear()
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    await state.clear()
    await message.answer(
        _support_settings_text(settings),
        reply_markup=admin_support_settings_menu(has_support=True),
    )


@router.message(ReceiptUploadStates.photo)
async def receipt_upload_photo(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    transaction_id = str(data.get("receipt_transaction_id") or "").strip()
    if transaction_id:
        await _handle_wallet_receipt_photo(message, seller_context, state, transaction_id=transaction_id)
        return
    order_id = str(data.get("receipt_order_id") or "").strip()
    if not order_id:
        await state.clear()
        await message.answer("درخواست ارسال فیش منقضی شد.", reply_markup=seller_buyer_menu())
        return
    if not message.photo:
        await message.answer(
            "\n".join(
                [
                    title("ارسال فیش"),
                    "لطفاً عکس فیش پرداخت را همینجا ارسال کنید.",
                    "",
                    "اگر منصرف شدید از دکمه لغو استفاده کنید.",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="home"),
        )
        return
    try:
        order_status = await seller_context.get_buyer_order_status(
            buyer_telegram_id=message.from_user.id,
            order_id=order_id,
        )
    except ValueError:
        await state.clear()
        await message.answer("سفارش پیدا نشد.", reply_markup=seller_buyer_menu())
        return
    if order_status.payment is None:
        await state.clear()
        await message.answer("برای این سفارش پرداختی ثبت نشده است.", reply_markup=seller_buyer_menu())
        return
    contacts = await seller_context.get_payment_notification_contacts(
        buyer_telegram_id=message.from_user.id,
    )
    caption = _receipt_notification_caption(
        buyer_telegram_id=message.from_user.id,
        order_status=order_status,
    )
    photo_file_id = message.photo[-1].file_id
    await _send_receipt_to_contact(
        message,
        chat_id=contacts.admin_telegram_id,
        photo_file_id=photo_file_id,
        caption=caption,
        payment_id=order_status.payment.id,
        include_actions=True,
    )
    if contacts.support_contact is not None and contacts.support_contact != contacts.admin_telegram_id:
        await _send_receipt_to_contact(
            message,
            chat_id=contacts.support_contact,
            photo_file_id=photo_file_id,
            caption=caption,
            payment_id=order_status.payment.id,
            include_actions=True,
        )
    await state.clear()
    await message.answer(
        "\n".join(
            [
                title("فیش ارسال شد"),
                "عکس فیش برای ادمین و پشتیبان ارسال شد.",
                "بعد از تایید پرداخت، سرویس شما ساخته یا بروزرسانی می‌شود.",
            ]
        ),
        reply_markup=payment_request_actions(order_id),
    )


async def _handle_wallet_receipt_photo(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext,
    *,
    transaction_id: str,
) -> None:
    if message.from_user is None:
        return
    if not message.photo:
        await message.answer(
            "\n".join(
                [
                    title("ارسال فیش شارژ کیف پول"),
                    "لطفاً عکس فیش شارژ کیف پول را همینجا ارسال کنید.",
                    "",
                    "اگر روش پرداخت دیگری مدنظر دارید، به پشتیبانی پیام بدهید.",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="wallet"),
        )
        return
    try:
        transaction = await seller_context.get_buyer_wallet_transaction(
            buyer_telegram_id=message.from_user.id,
            transaction_id=transaction_id,
        )
    except ValueError:
        await state.clear()
        await message.answer("درخواست شارژ کیف پول پیدا نشد.", reply_markup=wallet_charge_menu())
        return
    if transaction.status != "pending":
        await state.clear()
        await message.answer("این درخواست شارژ قبلاً بررسی شده است.", reply_markup=wallet_charge_menu())
        return
    contacts = await seller_context.get_payment_notification_contacts(
        buyer_telegram_id=message.from_user.id,
    )
    caption = _wallet_receipt_notification_caption(
        buyer_telegram_id=message.from_user.id,
        transaction=transaction,
    )
    photo_file_id = message.photo[-1].file_id
    await _send_wallet_receipt_to_contact(
        message,
        chat_id=contacts.admin_telegram_id,
        photo_file_id=photo_file_id,
        caption=caption,
        transaction_id=transaction.id,
        include_actions=True,
    )
    if contacts.support_contact is not None and contacts.support_contact != contacts.admin_telegram_id:
        await _send_wallet_receipt_to_contact(
            message,
            chat_id=contacts.support_contact,
            photo_file_id=photo_file_id,
            caption=caption,
            transaction_id=transaction.id,
            include_actions=False,
        )
    await state.clear()
    await message.answer(
        "\n".join(
            [
                title("فیش شارژ ارسال شد"),
                "عکس فیش برای ادمین و پشتیبان ارسال شد.",
                "بعد از تایید ادمین، مبلغ به کیف پول شما اضافه می‌شود.",
                "",
                "برای روش پرداخت دیگر، به پشتیبانی پیام بدهید.",
            ]
        ),
        reply_markup=wallet_charge_request_actions(transaction.id),
    )


@router.message(WalletChargeStates.amount)
async def wallet_charge_amount(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    raw_amount = (message.text or "").strip().replace(",", "")
    try:
        amount = float(raw_amount)
    except ValueError:
        await message.answer(
            "\n".join([title("شارژ دلخواه کیف پول"), "یک عدد معتبر بفرستید. مثال: 250000"]),
            reply_markup=wallet_charge_menu(),
        )
        return
    if amount <= 0:
        await message.answer(
            "\n".join([title("شارژ دلخواه کیف پول"), "مبلغ باید بیشتر از صفر باشد."]),
            reply_markup=wallet_charge_menu(),
        )
        return
    await state.update_data(wallet_amount=amount)
    await state.set_state(WalletChargeStates.confirm)
    await message.answer(
        _wallet_charge_confirm_text(amount),
        reply_markup=confirm_keyboard(
            scope="s",
            confirm_action="wallet_create",
            cancel_action="wallet_cancel",
        ),
    )


@router.message(WalletChargeStates.confirm)
async def wallet_charge_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("تایید شارژ کیف پول"), "از دکمه تایید یا لغو زیر پیش نمایش استفاده کنید."])
    )


@router.message(AdminPlanCreateStates.name)
async def admin_plan_create_name(
    message: Message,
    state: FSMContext,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    name = (message.text or "").strip()
    if not name or name.startswith("/"):
        await message.answer(
            "\n".join(
                [
                    title("افزودن پلن فروش"),
                    "اسم پلن نباید خالی یا دستور باشد.",
                    "مثال: پلن اقتصادی 30 روزه",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
        )
        return
    try:
        await seller_context.ensure_reseller_admin(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await state.clear()
        await message.answer("شما دسترسی ادمین فروشنده ندارید.", reply_markup=seller_buyer_menu())
        return
    data = await state.get_data()
    is_edit = data.get("admin_plan_mode") == "edit"
    await state.update_data(admin_plan={"name": name[:128]})
    await state.set_state(AdminPlanCreateStates.volume)
    await message.answer(
        "\n".join(
            [
                title("حجم پلن"),
                "حجم جدید پلن را به گیگابایت بفرستید." if is_edit else "حجم پلن را به گیگابایت بفرستید.",
                "",
                "فقط عدد وارد کنید. نامحدود نداریم.",
                "مثال: 50",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
    )


@router.message(AdminPlanCreateStates.volume)
async def admin_plan_create_volume(message: Message, state: FSMContext) -> None:
    data_limit_gb = _parse_positive_int(message.text)
    if data_limit_gb is None:
        await message.answer(
            "\n".join(
                [
                    title("حجم پلن"),
                    "حجم باید یک عدد صحیح بیشتر از صفر باشد.",
                    "",
                    "نامحدود نداریم.",
                    "مثال: 50",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
        )
        return
    data = await state.get_data()
    is_edit = data.get("admin_plan_mode") == "edit"
    spec = dict(data.get("admin_plan") or {})
    spec["data_limit_gb"] = data_limit_gb
    await state.update_data(admin_plan=spec)
    await state.set_state(AdminPlanCreateStates.days)
    await message.answer(
        "\n".join(
            [
                title("مدت پلن"),
                "مدت جدید پلن را به روز بفرستید." if is_edit else "مدت پلن را به روز بفرستید.",
                "",
                "فقط عدد وارد کنید.",
                "مثال: 30",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
    )


@router.message(AdminPlanCreateStates.days)
async def admin_plan_create_days(message: Message, state: FSMContext) -> None:
    duration_days = _parse_positive_int(message.text)
    if duration_days is None:
        await message.answer(
            "\n".join(
                [
                    title("مدت پلن"),
                    "مدت باید یک عدد صحیح بیشتر از صفر باشد.",
                    "مثال: 30",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
        )
        return
    data = await state.get_data()
    is_edit = data.get("admin_plan_mode") == "edit"
    spec = dict(data.get("admin_plan") or {})
    spec["duration_days"] = duration_days
    await state.update_data(admin_plan=spec)
    await state.set_state(AdminPlanCreateStates.price)
    await message.answer(
        "\n".join(
            [
                title("قیمت پلن"),
                "قیمت جدید پلن را به تومان بفرستید." if is_edit else "قیمت فروش پلن را به تومان بفرستید.",
                "",
                "فقط عدد وارد کنید.",
                "مثال: 120000",
            ]
        ),
        reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
    )


@router.message(AdminPlanCreateStates.price)
async def admin_plan_create_price(message: Message, state: FSMContext) -> None:
    price = _parse_positive_float(message.text)
    if price is None:
        await message.answer(
            "\n".join(
                [
                    title("قیمت پلن"),
                    "قیمت باید یک عدد بیشتر از صفر باشد.",
                    "مثال: 120000",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="admin_plans"),
        )
        return
    data = await state.get_data()
    is_edit = data.get("admin_plan_mode") == "edit"
    spec = dict(data.get("admin_plan") or {})
    spec["price"] = price
    await state.update_data(admin_plan=spec)
    await state.set_state(AdminPlanCreateStates.confirm)
    await message.answer(
        _admin_plan_confirm_text(spec, edited=is_edit),
        reply_markup=confirm_keyboard(
            scope="s",
            confirm_action="admin_plan_create",
            cancel_action="admin_plans",
        ),
    )


@router.message(AdminPlanCreateStates.confirm)
async def admin_plan_create_waiting_for_confirm(message: Message) -> None:
    await message.answer("برای ذخیره پلن از دکمه تایید استفاده کنید.")


@router.message(PurchaseCreateStates.username)
async def purchase_username_input(
    message: Message,
    state: FSMContext,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    raw_username = (message.text or "").strip()
    normalized_username = _normalize_service_username(raw_username)
    if normalized_username is None:
        await message.answer(
            "\n".join(
                [
                    title("👤 نام سرویس"),
                    "یک نام انگلیسی برای سرویس بفرستید.",
                    "فقط حروف انگلیسی کوچک، عدد و _ مجاز است.",
                    "طول مجاز: 3 تا 25 کاراکتر.",
                    "",
                    "مثال: sina_home",
                ]
            ),
            reply_markup=cancel_only_keyboard(scope="s", cancel_action="buy_cancel"),
        )
        return
    await state.update_data(buy_requested_username=normalized_username)
    data = await state.get_data()
    plan = await _find_plan(
        seller_context,
        plan_id=str(data.get("buy_plan_id")),
        purpose=PlanPurpose.PURCHASE,
    )
    if plan is None:
        await state.clear()
        await message.answer("پلن پیدا نشد. دوباره از خرید سرویس شروع کنید.")
        return
    await state.set_state(PurchaseCreateStates.coupon)
    await message.answer(
        _purchase_coupon_text(plan, requested_username=normalized_username),
        reply_markup=purchase_coupon_menu(),
    )


@router.message(PurchaseCreateStates.coupon)
async def purchase_coupon_input(
    message: Message,
    state: FSMContext,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    coupon = (message.text or "").strip()
    if not coupon or coupon.startswith("/"):
        await message.answer(
            "\n".join([title("کد تخفیف خرید"), "کد تخفیف را ارسال کنید یا ادامه بدون کد را بزنید."]),
            reply_markup=purchase_coupon_menu(),
        )
        return
    await _show_purchase_confirm(message, state, seller_context, coupon=coupon)


@router.message(PurchaseCreateStates.confirm)
async def purchase_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("تایید خرید"), "از دکمه تایید یا لغو زیر پیش نمایش استفاده کنید."])
    )


@router.message(RenewalCreateStates.coupon)
async def renewal_coupon_input(
    message: Message,
    state: FSMContext,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    coupon = (message.text or "").strip()
    if not coupon or coupon.startswith("/"):
        await message.answer(
            "\n".join([title("کد تخفیف تمدید"), "کد تخفیف را ارسال کنید یا ادامه بدون کد را بزنید."]),
            reply_markup=renewal_coupon_menu(),
        )
        return
    await _show_renewal_confirm(message, state, seller_context, coupon=coupon)


@router.message(RenewalCreateStates.plan)
async def renewal_waiting_for_plan(message: Message) -> None:
    await message.answer(
        "\n".join([title("تمدید سرویس"), "یکی از دکمه های پلن تمدید را انتخاب کنید."])
    )


@router.message(RenewalCreateStates.confirm)
async def renewal_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("تایید تمدید"), "از دکمه تایید یا لغو زیر پیش نمایش استفاده کنید."])
    )


@router.message(ExtraVolumeCreateStates.coupon)
async def extra_volume_coupon_input(
    message: Message,
    state: FSMContext,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    coupon = (message.text or "").strip()
    if not coupon or coupon.startswith("/"):
        await message.answer(
            "\n".join([title("کد تخفیف حجم اضافه"), "کد تخفیف را ارسال کنید یا ادامه بدون کد را بزنید."]),
            reply_markup=extra_volume_coupon_menu(),
        )
        return
    await _show_extra_volume_confirm(message, state, seller_context, coupon=coupon)


@router.message(ExtraVolumeCreateStates.plan)
async def extra_volume_waiting_for_plan(message: Message) -> None:
    await message.answer(
        "\n".join([title("حجم اضافه"), "یکی از دکمه های پلن حجم اضافه را انتخاب کنید."])
    )


@router.message(ExtraVolumeCreateStates.confirm)
async def extra_volume_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("تایید حجم اضافه"), "از دکمه تایید یا لغو زیر پیش نمایش استفاده کنید."])
    )


@router.message(TicketCreateStates.subject)
async def ticket_create_subject(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    subject = (message.text or "").strip()
    if not subject or subject.startswith("/"):
        await message.answer(
            "\n".join([title("ثبت تیکت"), "موضوع کوتاه تیکت را بفرستید؛ دستور ربات نفرستید."]),
            reply_markup=support_menu(),
        )
        return
    await state.update_data(ticket_subject=subject[:160])
    await state.set_state(TicketCreateStates.body)
    await message.answer(
        "\n".join(
            [
                title("ثبت تیکت"),
                "حالا متن پیام را برای پشتیبان بفرستید.",
                "",
                "Include device, app, and error details if possible.",
            ]
        ),
        reply_markup=support_menu(),
    )


@router.message(TicketCreateStates.body)
async def ticket_create_body(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    body = (message.text or "").strip()
    if not body or body.startswith("/"):
        await message.answer(
            "\n".join([title("ثبت تیکت"), "متن پیام را بفرستید؛ دستور ربات نفرستید."]),
            reply_markup=support_menu(),
        )
        return
    await state.update_data(ticket_body=body)
    await state.set_state(TicketCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("تایید ثبت تیکت"),
                f"موضوع: {data.get('ticket_subject')}",
                "",
                str(data.get("ticket_body")),
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="s",
            confirm_action="ticket_create",
            cancel_action="ticket_cancel",
        ),
    )


@router.message(TicketCreateStates.confirm)
async def ticket_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("تایید ثبت تیکت"), "از دکمه تایید یا لغو زیر پیش‌نمایش استفاده کنید."])
    )


@router.message(TicketReplyStates.buyer_body)
async def buyer_ticket_reply_body(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    body = (message.text or "").strip()
    if not body:
        await message.answer("یک پیام پاسخ غیرخالی بفرستید.")
        return
    data = await state.get_data()
    ticket_id = str(data.get("reply_ticket_id") or "").strip()
    if not ticket_id:
        await state.clear()
        await message.answer("پیش نویس پاسخ تیکت منقضی شد.", reply_markup=support_menu())
        return
    try:
        thread = await seller_context.reply_ticket_as_buyer(
            buyer_telegram_id=message.from_user.id,
            ticket_id=ticket_id,
            body=body,
        )
    except ValueError:
        await state.clear()
        await message.answer("تیکت پیدا نشد.", reply_markup=support_menu())
        return
    await state.clear()
    await _notify_support_about_ticket(
        message,
        seller_context,
        buyer_telegram_id=message.from_user.id,
        header="پاسخ جدید کاربر",
        ticket_id=thread.ticket.id,
        subject=thread.ticket.subject,
        body=body,
    )
    await message.answer(
        _ticket_thread_text(thread),
        reply_markup=buyer_ticket_actions(thread.ticket.id),
    )


@router.message(TicketReplyStates.admin_body)
async def admin_ticket_reply_body(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    body = (message.text or "").strip()
    if not body:
        await message.answer("یک پیام پاسخ غیرخالی بفرستید.")
        return
    data = await state.get_data()
    ticket_id = str(data.get("reply_ticket_id") or "").strip()
    if not ticket_id:
        await state.clear()
        await message.answer("پیش نویس پاسخ تیکت منقضی شد.", reply_markup=seller_admin_menu())
        return
    try:
        thread = await seller_context.reply_ticket_as_admin(
            admin_telegram_id=message.from_user.id,
            ticket_id=ticket_id,
            body=body,
        )
    except PermissionError:
        await state.clear()
        await message.answer("شما دسترسی ادمین فروشنده ندارید.", reply_markup=seller_buyer_menu())
        return
    except ValueError:
        await state.clear()
        await message.answer("تیکت پیدا نشد.", reply_markup=seller_admin_menu())
        return
    await state.clear()
    await message.answer(
        _ticket_thread_text(thread),
        reply_markup=admin_ticket_actions(thread.ticket.id),
    )


@router.message(SellerBroadcastCreateStates.title)
async def seller_broadcast_create_title(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    broadcast_title = (message.text or "").strip()
    if not broadcast_title or broadcast_title.startswith("/"):
        await message.answer(
            "\n".join([title("ساخت پیام همگانی"), "یک عنوان بفرستید؛ دستور ربات نفرستید."]),
            reply_markup=seller_admin_menu(),
        )
        return
    await state.update_data(seller_broadcast_title=broadcast_title[:160])
    await state.set_state(SellerBroadcastCreateStates.body)
    await message.answer(
        "\n".join(
            [
                title("ساخت پیام همگانی"),
                "متن پیام را بفرستید.",
                "",
                "This will be previewed before any draft is created.",
            ]
        ),
        reply_markup=seller_admin_menu(),
    )


@router.message(SellerBroadcastCreateStates.body)
async def seller_broadcast_create_body(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    broadcast_body = (message.text or "").strip()
    if not broadcast_body or broadcast_body.startswith("/"):
        await message.answer(
            "\n".join([title("ساخت پیام همگانی"), "متن پیام را بفرستید؛ دستور ربات نفرستید."]),
            reply_markup=seller_admin_menu(),
        )
        return
    await state.update_data(seller_broadcast_body=broadcast_body[:3500])
    await state.set_state(SellerBroadcastCreateStates.confirm)
    data = await state.get_data()
    await message.answer(
        "\n".join(
            [
                title("تایید پیش نویس پیام"),
                f"Title: {data.get('seller_broadcast_title')}",
                "",
                str(data.get("seller_broadcast_body")),
            ]
        ),
        reply_markup=confirm_keyboard(
            scope="s",
            confirm_action="broadcast_create",
            cancel_action="broadcast_cancel",
        ),
    )


@router.message(SellerBroadcastCreateStates.confirm)
async def seller_broadcast_create_waiting_for_confirmation(message: Message) -> None:
    await message.answer(
        "\n".join([title("تایید پیش نویس پیام"), "از دکمه تایید یا لغو زیر پیش نمایش استفاده کنید."])
    )


@router.message(SellerReportCustomStates.days)
async def seller_report_custom_days(
    message: Message,
    seller_context: SellerContextService,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    days = _parse_bounded_days(message.text)
    if days is None:
        await message.answer(
            "\n".join([title("گزارش فروش دلخواه"), "یک عدد بین ۱ تا ۳۶۵ بفرستید."]),
            reply_markup=seller_report_menu(),
        )
        return
    try:
        report = await seller_context.sales_report(admin_telegram_id=message.from_user.id, days=days)
    except PermissionError:
        await state.clear()
        await message.answer("شما دسترسی ادمین فروشنده ندارید.", reply_markup=seller_buyer_menu())
        return
    await state.clear()
    await message.answer(
        _format_report(f"Sales Report - Last {days} Days", report),
        reply_markup=seller_report_menu(),
    )


@router.message(AdminCustomerSearchStates.query)
async def admin_customer_search_query(
    message: Message,
    state: FSMContext,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    query = message.text.strip()
    if not query:
        await message.answer("Telegram ID، @username، نام کاربر یا نام VPN را بفرستید.")
        return
    try:
        customers = await seller_context.search_customers(
            admin_telegram_id=message.from_user.id,
            query=query,
        )
    except PermissionError:
        await state.clear()
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    await state.clear()
    await message.answer(
        _admin_customers_text(customers, heading=f"جستجوی کاربر: {query}"),
        reply_markup=admin_customers_menu(),
    )
    for item in customers[:8]:
        await message.answer(
            _admin_customer_card_text(item),
            reply_markup=admin_customer_card_actions(item.buyer.id),
        )


async def _send_legacy_start(message: Message, seller_context: SellerContextService) -> None:
    profile = await seller_context.register_buyer(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )
    await message.answer(
        "\n".join(
            [
                f"Welcome to {profile.seller_bot.name}.",
                f"Seller: {profile.reseller.display_name}",
                "",
                "Available now:",
                "/start - open your buyer profile",
                "/plans - show available VPN plans",
                "/buy - buy from wallet using buttons",
                "/renew <service_id> <plan_id> [coupon] - renew an existing service",
                "/my_services - show your VPN services",
                "/wallet - show wallet balance",
                "/charge_wallet <amount> - request wallet charge",
                "/trial - request a one-time trial",
                "/ticket <subject> | <message> - open support ticket",
                "/my_tickets - list your tickets",
                "/reply_ticket <ticket_id> <message>",
                "/admin - reseller admin panel",
                "",
                "Charge your wallet first. Service purchases are paid from wallet balance.",
            ]
        )
    )


@router.message(Command("plans"))
async def plans(message: Message, seller_context: SellerContextService) -> None:
    if await _blocked_by_forced_join(message):
        return
    available_plans = await seller_context.list_plans(purpose=PlanPurpose.PURCHASE)
    if not available_plans:
        await message.answer("هنوز هیچ پلن فعالی وجود ندارد.")
        return

    lines = ["پلن های موجود:"]
    for plan in available_plans:
        traffic = "نامحدود" if plan.data_limit_gb is None else f"{plan.data_limit_gb} گیگ"
        lines.append(
            f"- {plan.name}: {plan.price:,.0f} | {plan.duration_days} روز | {traffic} | کد={plan.id}"
        )
    await message.answer("\n".join(lines))
    for plan in available_plans[:5]:
        await message.answer(
            f"{plan.name}\nمبلغ: {plan.price:,.0f}\nمدت: {plan.duration_days} روز",
            reply_markup=plan_buy_button(plan.id),
        )


@router.message(Command("my_services"))
async def my_services(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    await _send_services_list(message, seller_context, buyer_telegram_id=message.from_user.id)


@router.message(Command("wallet"))
async def wallet(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    wallet_info = await seller_context.list_buyer_wallet(
        buyer_telegram_id=message.from_user.id,
    )
    balance = wallet_info.buyer.wallet_balance if wallet_info.buyer else 0
    lines = [f"موجودی کیف پول: {balance:,.0f}", "", "تراکنش های اخیر:"]
    if not wallet_info.transactions:
        lines.append("- موردی وجود ندارد")
    for transaction in wallet_info.transactions[:10]:
        lines.append(
            f"- {transaction.transaction_type} | {transaction.status} | {transaction.amount:,.0f}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("charge_wallet"))
async def charge_wallet(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    raw_amount = (command.args or "").strip()
    try:
        amount = float(raw_amount)
    except ValueError:
        await message.answer("فرمت دستور: /charge_wallet <amount>")
        return
    try:
        charge = await seller_context.request_wallet_charge(
            buyer_telegram_id=message.from_user.id,
            amount=amount,
        )
    except ValueError as exc:
        if str(exc) == "invalid_amount":
            await message.answer("مبلغ باید بیشتر از صفر باشد.")
            return
        raise
    await message.answer(
        _wallet_charge_request_text(charge),
        reply_markup=wallet_charge_request_actions(charge.transaction.id),
    )


@router.message(Command("trial"))
async def trial(
    message: Message,
    provisioning_service: ProvisioningService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    try:
        service = await provisioning_service.provision_trial(
            buyer_telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code,
        )
    except ValueError as exc:
        if str(exc) == "trial_disabled":
            await message.answer("سرویس تستی فعلاً غیرفعال است.")
            return
        if str(exc) == "trial_already_used":
            await message.answer("شما قبلاً سرویس تستی خود را استفاده کرده اید.")
            return
        if str(exc) == "panel_assignment_not_found":
            await message.answer("سرویس تستی در دسترس نیست چون هیچ پنلی اختصاص داده نشده است.")
            return
        raise

    text = "\n".join(
        [
            "سرویس تستی VPN ساخته شد.",
            f"کد سرویس: {service.id}",
            f"نام کاربری: {service.marzban_username}",
            f"حجم: {service.data_limit_gb} گیگ",
            f"انقضا: {service.expire_at.isoformat() if service.expire_at else 'نامحدود'}",
            f"لینک اشتراک: {service.subscription_url or '-'}",
        ]
    )
    if not service.subscription_url:
        await message.answer(text)
        return
    qr_file = BufferedInputFile(
        make_qr_png_bytes(service.subscription_url),
        filename=f"{service.marzban_username}.png",
    )
    await message.answer_photo(qr_file, caption=text)


@router.message(Command("ticket"))
async def ticket(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    raw = (command.args or "").strip()
    if " | " not in raw:
        await message.answer("فرمت دستور: /ticket <subject> | <message>")
        return
    subject, body = [part.strip() for part in raw.split(" | ", maxsplit=1)]
    if not subject or not body:
        await message.answer("فرمت دستور: /ticket <subject> | <message>")
        return
    thread = await seller_context.open_ticket(
        buyer_telegram_id=message.from_user.id,
        subject=subject,
        body=body,
    )
    await _notify_support_about_ticket(
        message,
        seller_context,
        buyer_telegram_id=message.from_user.id,
        header="تیکت جدید",
        ticket_id=thread.ticket.id,
        subject=thread.ticket.subject,
        body=body,
    )
    await message.answer(
        f"تیکت ثبت شد.\nکد تیکت: {thread.ticket.id}\nموضوع: {thread.ticket.subject}"
    )


@router.message(Command("my_tickets"))
async def my_tickets(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    tickets = await seller_context.list_my_tickets(buyer_telegram_id=message.from_user.id)
    if not tickets:
        await message.answer("شما هیچ تیکتی ندارید.")
        return
    lines = ["تیکت های شما:"]
    for ticket_item in tickets:
        lines.append(f"- {ticket_item.id} | {ticket_item.status} | {ticket_item.subject}")
    await message.answer("\n".join(lines))


@router.message(Command("reply_ticket"))
async def reply_ticket(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) != 2:
        await message.answer("فرمت دستور: /reply_ticket <ticket_id> <message>")
        return
    try:
        thread = await seller_context.reply_ticket_as_buyer(
            buyer_telegram_id=message.from_user.id,
            ticket_id=args[0],
            body=args[1],
        )
    except ValueError as exc:
        if str(exc) == "ticket_not_found":
            await message.answer("تیکت پیدا نشد.")
            return
        raise
    await _notify_support_about_ticket(
        message,
        seller_context,
        buyer_telegram_id=message.from_user.id,
        header="پاسخ جدید کاربر",
        ticket_id=thread.ticket.id,
        subject=thread.ticket.subject,
        body=args[1],
    )
    await message.answer(f"پاسخ به تیکت {thread.ticket.id} اضافه شد.")


@router.message(Command("buy"))
async def buy(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    await message.answer(
        "\n".join(
            [
                title("🛒 خرید سرویس"),
                "خرید فقط از طریق کیف پول انجام می‌شود.",
                "از دکمه‌های پلن‌ها استفاده کنید تا نام سرویس را وارد کنید و پرداخت از کیف پول انجام شود.",
            ]
        ),
        reply_markup=seller_section_menu("plans"),
    )


@router.message(Command("renew"))
async def renew(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    if await _blocked_by_forced_join(message):
        return
    args = (command.args or "").strip().split(maxsplit=2)
    if len(args) < 2:
        await message.answer("فرمت دستور: /renew <service_id> <plan_id> [coupon]")
        return
    try:
        payment_request = await seller_context.request_renewal_payment(
            buyer_telegram_id=message.from_user.id,
            service_id=args[0],
            plan_id=args[1],
            coupon_code=args[2] if len(args) == 3 else None,
        )
    except ValueError as exc:
        if str(exc) == "service_not_found":
            await message.answer("سرویس پیدا نشد. برای دیدن سرویس ها از /my_services استفاده کنید.")
            return
        if str(exc) == "plan_not_found":
            await message.answer("پلن پیدا نشد یا غیرفعال است. از /plans استفاده کنید.")
            return
        if str(exc) == "discount_not_found":
            await message.answer("کد تخفیف پیدا نشد، غیرفعال است یا ظرفیت آن تمام شده است.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "درخواست پرداخت تمدید ساخته شد.",
                f"کد سفارش: {payment_request.order.id}",
                f"کد پرداخت: {payment_request.payment.id}",
                f"پلن: {payment_request.plan.name}",
                f"مبلغ: {payment_request.payment.amount:,.0f}",
                "",
                payment_request.instructions,
            ]
        ),
        reply_markup=payment_request_actions(payment_request.order.id),
    )


@router.message(Command("admin"))
async def admin(message: Message, seller_context: SellerContextService) -> None:
    if message.from_user is None:
        return
    try:
        pending = await seller_context.list_pending_payments(
            admin_telegram_id=message.from_user.id,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return

    lines = [
        title("مدیریت فروشنده"),
        "یکی از عملیات زیر را انتخاب کنید.",
        "",
        "پرداخت های در انتظار:",
    ]
    if not pending:
        lines.append("- موردی وجود ندارد")
    for item in pending:
        lines.append(
            f"- پرداخت={item.payment.id} | سفارش={item.order.id} | "
            f"پلن={item.plan.name} | مبلغ={item.payment.amount:,.0f}"
        )
    pending_wallet = await seller_context.list_pending_wallet_charges(
        admin_telegram_id=message.from_user.id,
    )
    lines.extend(["", "شارژهای کیف پول در انتظار:"])
    if not pending_wallet:
        lines.append("- موردی وجود ندارد")
    for item in pending_wallet:
        lines.append(f"- تراکنش={item.id} | خریدار={item.owner_id} | مبلغ={item.amount:,.0f}")
    open_tickets = await seller_context.list_open_tickets(admin_telegram_id=message.from_user.id)
    lines.extend(["", "تیکت های باز:"])
    if not open_tickets:
        lines.append("- موردی وجود ندارد")
    for ticket_item in open_tickets:
        lines.append(
            f"- تیکت={ticket_item.id} | موضوع={ticket_item.subject} | وضعیت={ticket_item.status}"
        )
    await message.answer("\n".join(lines), reply_markup=seller_admin_menu())


@router.message(Command("approve_payment"))
async def approve_payment(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    payment_id = (command.args or "").strip()
    if not payment_id:
        await message.answer("فرمت دستور: /approve_payment <payment_id>")
        return
    try:
        approved = await seller_context.approve_payment(
            admin_telegram_id=message.from_user.id,
            payment_id=payment_id,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    except ValueError as exc:
        if str(exc) == "payment_not_found":
            await message.answer("پرداخت در انتظار پیدا نشد.")
            return
        raise

    await message.answer(
        "\n".join(
            [
                "پرداخت تایید شد.",
                f"کد پرداخت: {approved.payment.id}",
                f"کد سفارش: {approved.order.id}",
                f"وضعیت سفارش: {approved.order.status}",
                "",
                "مرحله بعدی ساخت سرویس است.",
            ]
        )
    )


@router.message(Command("approve_wallet_charge"))
async def approve_wallet_charge(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    transaction_id = (command.args or "").strip()
    if not transaction_id:
        await message.answer("فرمت دستور: /approve_wallet_charge <transaction_id>")
        return
    try:
        approved = await seller_context.approve_wallet_charge(
            admin_telegram_id=message.from_user.id,
            transaction_id=transaction_id,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    except ValueError as exc:
        if str(exc) == "wallet_charge_not_found":
            await message.answer("شارژ کیف پول در انتظار پیدا نشد.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "شارژ کیف پول تایید شد.",
                f"کد تراکنش: {approved.transaction.id}",
                f"مبلغ: {approved.transaction.amount:,.0f}",
            ]
        )
    )


@router.message(Command("admin_reply_ticket"))
async def admin_reply_ticket(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) != 2:
        await message.answer("فرمت دستور: /admin_reply_ticket <ticket_id> <message>")
        return
    try:
        thread = await seller_context.reply_ticket_as_admin(
            admin_telegram_id=message.from_user.id,
            ticket_id=args[0],
            body=args[1],
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    except ValueError as exc:
        if str(exc) == "ticket_not_found":
            await message.answer("تیکت پیدا نشد.")
            return
        raise
    await message.answer(f"پاسخ ادمین به تیکت {thread.ticket.id} اضافه شد.")


@router.message(Command("close_ticket"))
async def close_ticket(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    ticket_id = (command.args or "").strip()
    if not ticket_id:
        await message.answer("فرمت دستور: /close_ticket <ticket_id>")
        return
    try:
        closed = await seller_context.close_ticket(
            admin_telegram_id=message.from_user.id,
            ticket_id=ticket_id,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    except ValueError as exc:
        if str(exc) == "ticket_not_found":
            await message.answer("تیکت پیدا نشد.")
            return
        raise
    await message.answer(f"تیکت بسته شد.\nکد تیکت: {closed.id}")


@router.message(Command("broadcast"))
async def broadcast(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    raw = (command.args or "").strip()
    if " | " not in raw:
        await message.answer("فرمت دستور: /broadcast <title> | <message>")
        return
    title, body = [part.strip() for part in raw.split(" | ", maxsplit=1)]
    if not title or not body:
        await message.answer("فرمت دستور: /broadcast <title> | <message>")
        return
    try:
        draft = await seller_context.create_broadcast(
            admin_telegram_id=message.from_user.id,
            title=title,
            body=body,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    await message.answer(
        "\n".join(
            [
                "پیش نویس پیام همگانی ساخته شد.",
                f"کد پیام: {draft.broadcast.id}",
                f"تعداد گیرنده ها: {len(draft.recipients)}",
                f"ارسال با دستور: /send_broadcast {draft.broadcast.id}",
            ]
        )
    )


@router.message(Command("send_broadcast"))
async def send_broadcast(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    broadcast_id = (command.args or "").strip()
    if not broadcast_id:
        await message.answer("فرمت دستور: /send_broadcast <broadcast_id>")
        return
    try:
        draft = await seller_context.get_broadcast_recipients(
            admin_telegram_id=message.from_user.id,
            broadcast_id=broadcast_id,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    except ValueError as exc:
        if str(exc) == "broadcast_not_found":
            await message.answer("پیام همگانی پیدا نشد.")
            return
        raise

    delivered: set[int] = set()
    text = f"{draft.broadcast.title}\n\n{draft.broadcast.body}"
    for recipient in draft.recipients:
        try:
            await message.bot.send_message(recipient.telegram_user_id, text)
        except TelegramAPIError:
            continue
        delivered.add(recipient.telegram_user_id)
    sent = await seller_context.mark_broadcast_sent(
        admin_telegram_id=message.from_user.id,
        broadcast_id=draft.broadcast.id,
        delivered_telegram_ids=delivered,
    )
    await message.answer(
        f"Broadcast sent.\nDelivered: {sent.sent_count}/{sent.target_count}\nID: {sent.id}"
    )


@router.message(Command("sales_report"))
async def sales_report(
    message: Message,
    command: CommandObject,
    seller_context: SellerContextService,
) -> None:
    if message.from_user is None:
        return
    days = _parse_days(command.args)
    try:
        report = await seller_context.sales_report(
            admin_telegram_id=message.from_user.id,
            days=days,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    await message.answer(_format_report(f"Sales report - last {days} day(s)", report))


def _parse_days(raw: str | None) -> int:
    if not raw:
        return 1
    try:
        days = int(raw.strip())
    except ValueError:
        return 1
    return max(1, min(days, 365))


def _parse_bounded_days(raw: str | None) -> int | None:
    try:
        days = int((raw or "").strip().replace(",", ""))
    except ValueError:
        return None
    if days < 1 or days > 365:
        return None
    return days


def _buyer_dashboard_text(*, seller_name: str, reseller_name: str) -> str:
    return "\n".join(
        [
            title(f"🐝 {seller_name}"),
            f"فروشنده: {reseller_name}",
            "",
            "🚀 یکی از دکمه های زیر را انتخاب کنید !",
        ]
    )


async def _plans_text(seller_context: SellerContextService) -> str:
    plans = await seller_context.list_plans(purpose=PlanPurpose.PURCHASE)
    return _plans_text_from_list(plans)


def _plans_text_from_list(plans) -> str:
    if not plans:
        return "\n".join([title("🛒 خرید سرویس"), "😢 در حال حاضر سرویسی برای خرید موجود نمی‌باشد!"])
    rows = []
    for plan in plans[:12]:
        traffic = "نامحدود" if plan.data_limit_gb is None else f"{plan.data_limit_gb} گیگ"
        rows.append(
            f"▫️ {plan.name} | {plan.price:,.0f} تومان | {plan.duration_days} روز | {traffic} | کد: {short_id(plan.id)}"
        )
    rows.extend(["", "👇🏻 برای خرید و فعالسازی سرویس، یکی از دکمه های پلن را انتخاب کنید."])
    return "\n".join([title("🛒 خرید سرویس"), section("📲 سرویس‌های موجود", rows)])


async def _send_services_list(
    message: Message,
    seller_context: SellerContextService,
    *,
    buyer_telegram_id: int,
) -> None:
    services = await seller_context.list_buyer_services(buyer_telegram_id=buyer_telegram_id)
    await message.answer(
        _services_text_from_list(services),
        reply_markup=service_list_menu(services),
    )


async def _services_text(seller_context: SellerContextService, *, buyer_telegram_id: int) -> str:
    services = await seller_context.list_buyer_services(buyer_telegram_id=buyer_telegram_id)
    return _services_text_from_list(services)


def _services_text_from_list(services) -> str:
    if not services:
        return "\n".join([title("🛍 سرویس های من"), "❌ شما در ربات ما هیچ سرویس فعالی ندارید!"])
    rows = []
    for service in services[:12]:
        traffic = "نامحدود" if service.data_limit_gb is None else f"{service.data_limit_gb} گیگ"
        expire = service.expire_at.date().isoformat() if service.expire_at else "نامحدود"
        rows.append(
            f"▫️ {service.marzban_username} | {status_label('active' if service.is_active else 'disabled')} | "
            f"{traffic} | اعتبار تا: {expire} | کد: {short_id(service.id)}"
        )
    rows.extend(["", "🎯 یکی از سرویس های خود را انتخاب کنید تا وارد پنل تنظیمات و مدیریت سرویس شوید."])
    return "\n".join([title("🛍 سرویس های من"), section("سرویس ها", rows)])


async def _find_buyer_service(
    seller_context: SellerContextService,
    *,
    buyer_telegram_id: int,
    service_id: str,
):
    services = await seller_context.list_buyer_services(buyer_telegram_id=buyer_telegram_id)
    return next((service for service in services if service.id == service_id), None)


async def _find_plan(
    seller_context: SellerContextService,
    *,
    plan_id: str,
    purpose: PlanPurpose | None = PlanPurpose.PURCHASE,
):
    plans = await seller_context.list_plans(purpose=purpose)
    return next((plan for plan in plans if plan.id == plan_id), None)


def _service_card_text(service) -> str:
    traffic = "نامحدود" if service.data_limit_gb is None else f"{service.data_limit_gb} گیگ"
    expire = service.expire_at.date().isoformat() if service.expire_at else "نامحدود"
    return "\n".join(
        [
            title("🌐 اطلاعات سرویس"),
            f"کد سرویس: {short_id(service.id)}",
            f"نام کاربری: {service.marzban_username}",
            f"وضعیت سرویس: {status_label('active' if service.is_active else 'disabled')}",
            f"حجم سرویس: {traffic}",
            f"فعال تا تاریخ: {expire}",
        ]
    )


def _service_detail_text(service) -> str:
    traffic = "نامحدود" if service.data_limit_gb is None else f"{service.data_limit_gb} گیگ"
    expire = service.expire_at.isoformat() if service.expire_at else "نامحدود"
    subscription = service.subscription_url or "-"
    return "\n".join(
        [
            title("🌐 اطلاعات سرویس شما"),
            f"🔎 وضعیت سرویس: {status_label('active' if service.is_active else 'disabled')}",
            f"👤 نام کاربری: {service.marzban_username}",
            f"♾ حجم سرویس: {traffic}",
            f"📅 فعال تا تاریخ: {expire}",
            f"#️⃣ کد سرویس: {service.id}",
            "",
            "🔗 لینک اتصال:",
            subscription,
        ]
    )


def _service_guide_text(service_id: str) -> str:
    return "\n".join(
        [
            title("🔗 راهنمای اتصال"),
            f"کد سرویس: {service_id}",
            "",
            "1️⃣ لینک اشتراک را از بخش «دریافت لینک اشتراک» کپی کنید.",
            "2️⃣ برنامه Hiddify، V2RayNG، Streisand یا Nekobox را باز کنید.",
            "3️⃣ لینک را به عنوان Subscription یا از Clipboard اضافه کنید.",
            "4️⃣ اشتراک را Update کنید و سپس متصل شوید.",
        ]
    )


async def _renewal_text(seller_context: SellerContextService, *, service_id: str) -> str:
    plans = await seller_context.list_plans(purpose=PlanPurpose.PURCHASE)
    return _renewal_text_from_list(plans, service_id=service_id)


def _renewal_text_from_list(plans, *, service_id: str) -> str:
    if not plans:
        return "\n".join([title("🔄 تمدید و افزایش حجم"), "❌ پلنی برای تمدید سرویس یافت نشد."])
    rows = []
    for plan in plans[:12]:
        traffic = "نامحدود" if plan.data_limit_gb is None else f"+{plan.data_limit_gb} گیگ"
        rows.append(
            f"▫️ {plan.name} | {plan.price:,.0f} تومان | +{plan.duration_days} روز | {traffic}"
        )
    rows.extend(
        [
            "",
            f"کد سرویس: {short_id(service_id)}",
            "👇🏻 یک پلن انتخاب کنید؛ مدت زمان و حجم همان پلن به سرویس فعلی اضافه می‌شود.",
        ]
    )
    return "\n".join([title("🔄 تمدید و افزایش حجم"), section("پلن ها", rows)])


def _renewal_plan_card_text(plan) -> str:
    traffic = "نامحدود" if plan.data_limit_gb is None else f"+{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("🔄 پلن تمدید و افزایش حجم"),
            f"نام پلن: {plan.name}",
            f"قیمت: {plan.price:,.0f} تومان",
            f"افزایش زمان: +{plan.duration_days} روز",
            f"حجم: {traffic}",
            f"کد: {short_id(plan.id)}",
        ]
    )


async def _extra_volume_text(seller_context: SellerContextService, *, service_id: str) -> str:
    plans = await seller_context.list_plans(purpose=PlanPurpose.EXTRA_VOLUME)
    if not plans:
        return "\n".join([title("خرید حجم اضافه"), "❌ پلنی برای خرید حجم اضافه یافت نشد."])
    rows = []
    for plan in plans[:12]:
        traffic = "نامحدود" if plan.data_limit_gb is None else f"+{plan.data_limit_gb} گیگ"
        rows.append(f"▫️ {plan.name} | {plan.price:,.0f} تومان | {traffic}")
    rows.extend(["", f"کد سرویس: {short_id(service_id)}", "👇🏻 یکی از پلن‌های زیر را برای افزایش حجم اضافه انتخاب کنید."])
    return "\n".join([title("خرید حجم اضافه"), section("پلن ها", rows)])


def _extra_volume_plan_card_text(plan) -> str:
    traffic = "نامحدود" if plan.data_limit_gb is None else f"+{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("پلن حجم اضافه"),
            f"نام پلن: {plan.name}",
            f"قیمت: {plan.price:,.0f} تومان",
            f"حجم: {traffic}",
            f"کد: {short_id(plan.id)}",
        ]
    )


def _purchase_username_text(plan) -> str:
    traffic = "نامحدود" if plan.data_limit_gb is None else f"{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("👤 نام سرویس"),
            f"پلن انتخابی: {plan.name}",
            f"مدت زمان: {plan.duration_days} روز",
            f"حجم: {traffic}",
            f"قیمت: {plan.price:,.0f} تومان",
            "",
            "یک نام انگلیسی برای اکانت VPN بفرستید.",
            "بعد از ساخت، چند کاراکتر رندوم به انتهای آن اضافه می‌شود تا تکراری نشود.",
            "",
            "مثال: sina_home",
        ]
    )


def _purchase_coupon_text(plan, *, requested_username: str | None = None) -> str:
    traffic = "نامحدود" if plan.data_limit_gb is None else f"{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("🎁 کد تخفیف"),
            f"پلن انتخابی: {plan.name}",
            f"نام سرویس: {requested_username or '-'}",
            f"قیمت: {plan.price:,.0f} تومان",
            f"مدت زمان: {plan.duration_days} روز",
            f"حجم: {traffic}",
            "",
            "اگر کد تخفیف دارید ارسال کنید، در غیر این صورت ادامه بدون کد را بزنید.",
        ]
    )


def _purchase_confirm_text(quote, *, requested_username: str | None = None) -> str:
    plan = quote.plan
    original_amount = float(plan.price)
    rows = [
        title("ℹ️ فاکتور سرویس"),
        f"پلن انتخابی: {plan.name}",
        f"نام سرویس: {requested_username or '-'}",
        f"مدت زمان: {plan.duration_days} روز",
        f"مبلغ سرویس: {original_amount:,.0f} تومان",
        f"کد تخفیف: {quote.coupon_code or '-'}",
        f"مبلغ کسر از کیف پول: {quote.amount:,.0f} تومان",
    ]
    if quote.amount < original_amount:
        rows.append(f"مبلغ تخفیف: {original_amount - quote.amount:,.0f} تومان")
    rows.extend(["", "👇🏻 با تایید، مبلغ از کیف پول کم می‌شود و سرویس خودکار ساخته می‌شود."])
    return "\n".join(rows)


async def _show_purchase_confirm(
    target: CallbackQuery | Message,
    state: FSMContext,
    seller_context: SellerContextService,
    *,
    coupon: str | None,
) -> None:
    data = await state.get_data()
    plan_id = data.get("buy_plan_id")
    if not plan_id:
        if isinstance(target, CallbackQuery):
            await target.answer("پیش نویس خرید پیدا نشد.", show_alert=True)
        else:
            await target.answer("پیش نویس خرید پیدا نشد. دوباره از خرید سرویس شروع کنید.")
        await state.clear()
        return
    try:
        quote = await seller_context.quote_card_to_card_payment(
            plan_id=str(plan_id),
            coupon_code=coupon,
        )
    except ValueError as exc:
        if str(exc) == "discount_not_found":
            if isinstance(target, CallbackQuery):
                await target.answer("کد تخفیف پیدا نشد.", show_alert=True)
            else:
                await target.answer("کد تخفیف پیدا نشد. کد دیگری بفرستید یا ادامه بدون کد را بزنید.")
            return
        if str(exc) == "plan_not_found":
            if isinstance(target, CallbackQuery):
                await target.answer("پلن پیدا نشد.", show_alert=True)
            else:
                await target.answer("پلن پیدا نشد. دوباره از خرید سرویس شروع کنید.")
            await state.clear()
            return
        raise
    requested_username = data.get("buy_requested_username")
    await state.update_data(buy_coupon=quote.coupon_code, buy_amount=quote.amount)
    await state.set_state(PurchaseCreateStates.confirm)
    text = _purchase_confirm_text(quote, requested_username=str(requested_username or ""))
    if isinstance(target, CallbackQuery):
        if target.message is not None:
            await target.message.edit_text(text, reply_markup=purchase_confirm_menu())
    else:
        await target.answer(text, reply_markup=purchase_confirm_menu())


def _renewal_coupon_text(service, plan) -> str:
    traffic = "نامحدود" if plan.data_limit_gb is None else f"+{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("🎁 کد تخفیف تمدید"),
            f"سرویس انتخابی: {service.marzban_username}",
            f"پلن انتخابی: {plan.name}",
            f"افزایش زمان: +{plan.duration_days} روز",
            f"افزایش حجم: {traffic}",
            f"مبلغ: {plan.price:,.0f} تومان",
            "",
            "اگر کد تخفیف دارید ارسال کنید، در غیر این صورت ادامه بدون کد را بزنید.",
        ]
    )


def _renewal_confirm_text(service, plan, *, coupon: str | None) -> str:
    traffic = "نامحدود" if plan.data_limit_gb is None else f"+{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("🧾 فاکتور تمدید و افزایش حجم"),
            f"سرویس انتخابی: {service.marzban_username}",
            f"پلن انتخابی: {plan.name}",
            f"افزایش زمان: +{plan.duration_days} روز",
            f"افزایش حجم: {traffic}",
            f"مبلغ تمدید: {plan.price:,.0f} تومان",
            f"کد تخفیف: {coupon or '-'}",
            "",
            "✅ با تایید، زمان و حجم این پلن به سرویس فعلی اضافه می‌شود.",
        ]
    )


def _extra_volume_coupon_text(service, plan) -> str:
    traffic = "نامحدود" if plan.data_limit_gb is None else f"+{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("🎁 کد تخفیف حجم اضافه"),
            f"سرویس انتخابی: {service.marzban_username}",
            f"پلن انتخابی: {plan.name}",
            f"حجم: {traffic}",
            f"مبلغ: {plan.price:,.0f} تومان",
            "",
            "اگر کد تخفیف دارید ارسال کنید، در غیر این صورت ادامه بدون کد را بزنید.",
        ]
    )


def _extra_volume_confirm_text(service, plan, *, coupon: str | None) -> str:
    traffic = "نامحدود" if plan.data_limit_gb is None else f"+{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("🟢 فاکتور خرید حجم اضافه"),
            f"سرویس انتخابی: {service.marzban_username}",
            f"پلن انتخابی: {plan.name}",
            f"حجم اضافه: {traffic}",
            f"قیمت فاکتور: {plan.price:,.0f} تومان",
            f"کد تخفیف: {coupon or '-'}",
            "",
            "ℹ️ در صورت تایید و افزایش حجم سرویس روی دکمه تایید کلیک کنید.",
        ]
    )


async def _show_renewal_confirm(
    target: CallbackQuery | Message,
    state: FSMContext,
    seller_context: SellerContextService,
    *,
    coupon: str | None,
) -> None:
    from_user = target.from_user
    data = await state.get_data()
    service_id = data.get("renew_service_id")
    plan_id = data.get("renew_plan_id")
    if not service_id or not plan_id:
        if isinstance(target, CallbackQuery):
            await target.answer("پیش نویس تمدید پیدا نشد.", show_alert=True)
        else:
            await target.answer("پیش نویس تمدید پیدا نشد. دوباره از سرویس های من شروع کنید.")
        await state.clear()
        return
    service = await _find_buyer_service(
        seller_context,
        buyer_telegram_id=from_user.id,
        service_id=str(service_id),
    )
    plan = await _find_plan(seller_context, plan_id=str(plan_id), purpose=PlanPurpose.PURCHASE)
    if service is None or plan is None:
        if isinstance(target, CallbackQuery):
            await target.answer("پیش نویس تمدید دیگر معتبر نیست.", show_alert=True)
        else:
            await target.answer("پیش نویس تمدید دیگر معتبر نیست. دوباره از سرویس های من شروع کنید.")
        await state.clear()
        return
    await state.update_data(renew_coupon=coupon)
    await state.set_state(RenewalCreateStates.confirm)
    text = _renewal_confirm_text(service, plan, coupon=coupon)
    if isinstance(target, CallbackQuery):
        if target.message is not None:
            await target.message.edit_text(text, reply_markup=renewal_confirm_menu())
    else:
        await target.answer(text, reply_markup=renewal_confirm_menu())


async def _show_extra_volume_confirm(
    target: CallbackQuery | Message,
    state: FSMContext,
    seller_context: SellerContextService,
    *,
    coupon: str | None,
) -> None:
    from_user = target.from_user
    data = await state.get_data()
    service_id = data.get("extra_service_id")
    plan_id = data.get("extra_plan_id")
    if not service_id or not plan_id:
        if isinstance(target, CallbackQuery):
            await target.answer("پیش نویس حجم اضافه پیدا نشد.", show_alert=True)
        else:
            await target.answer("پیش نویس حجم اضافه پیدا نشد. دوباره از سرویس های من شروع کنید.")
        await state.clear()
        return
    service = await _find_buyer_service(
        seller_context,
        buyer_telegram_id=from_user.id,
        service_id=str(service_id),
    )
    plan = await _find_plan(seller_context, plan_id=str(plan_id), purpose=PlanPurpose.EXTRA_VOLUME)
    if service is None or plan is None:
        if isinstance(target, CallbackQuery):
            await target.answer("پیش نویس حجم اضافه دیگر معتبر نیست.", show_alert=True)
        else:
            await target.answer("پیش نویس حجم اضافه دیگر معتبر نیست. دوباره از سرویس های من شروع کنید.")
        await state.clear()
        return
    await state.update_data(extra_coupon=coupon)
    await state.set_state(ExtraVolumeCreateStates.confirm)
    text = _extra_volume_confirm_text(service, plan, coupon=coupon)
    if isinstance(target, CallbackQuery):
        if target.message is not None:
            await target.message.edit_text(text, reply_markup=extra_volume_confirm_menu())
    else:
        await target.answer(text, reply_markup=extra_volume_confirm_menu())


async def _wallet_text(seller_context: SellerContextService, *, buyer_telegram_id: int) -> str:
    wallet_info = await seller_context.list_buyer_wallet(buyer_telegram_id=buyer_telegram_id)
    balance = wallet_info.buyer.wallet_balance if wallet_info.buyer else 0
    rows = [
        f"- {transaction.transaction_type} | {status_label(transaction.status)} | {transaction.amount:,.0f}"
        for transaction in wallet_info.transactions[:8]
    ]
    rows.extend(["", "💵 یکی از مبلغ‌های زیر را جهت شارژ حساب انتخاب کنید."])
    return "\n".join([title("👤 پروفایل"), f"💰 موجودی: {balance:,.0f} تومان", "", section("تراکنش های اخیر", rows)])


def _wallet_transaction_card_text(transaction) -> str:
    return "\n".join(
        [
            title("تراکنش کیف پول"),
            f"کد تراکنش: {transaction.id}",
            f"نوع: {transaction.transaction_type}",
            f"وضعیت: {status_label(transaction.status)}",
            f"مبلغ: {transaction.amount:,.0f}",
        ]
    )


def _wallet_transaction_detail_text(transaction) -> str:
    return "\n".join(
        [
            title("جزئیات تراکنش"),
            f"کد تراکنش: {transaction.id}",
            f"نوع: {transaction.transaction_type}",
            f"وضعیت: {status_label(transaction.status)}",
            f"مبلغ: {transaction.amount:,.0f}",
            f"پرداخت مرتبط: {transaction.related_payment_id or '-'}",
            f"تایید کننده: {transaction.approved_by_telegram_id or '-'}",
            f"زمان ساخت: {transaction.created_at.isoformat()}",
            "",
            f"یادداشت: {transaction.note or '-'}",
        ]
    )


async def _buyer_tickets_text(
    seller_context: SellerContextService,
    *,
    buyer_telegram_id: int,
) -> str:
    tickets = await seller_context.list_my_tickets(buyer_telegram_id=buyer_telegram_id)
    rows = [
        f"- {ticket_item.id} | {status_label(ticket_item.status)} | {ticket_item.subject}"
        for ticket_item in tickets[:12]
    ]
    rows.extend(["", "برای مشاهده جزئیات یا پاسخ، روی کارت تیکت بزنید."])
    return "\n".join([title("تیکت های من"), section("تیکت ها", rows)])


def _ticket_card_text(ticket_item) -> str:
    return "\n".join(
        [
            title("تیکت"),
            f"کد تیکت: {ticket_item.id}",
            f"موضوع: {ticket_item.subject}",
            f"وضعیت: {status_label(ticket_item.status)}",
        ]
    )


def _ticket_thread_text(thread) -> str:
    rows = [
        title("جزئیات تیکت"),
        f"کد تیکت: {thread.ticket.id}",
        f"موضوع: {thread.ticket.subject}",
        f"وضعیت: {status_label(thread.ticket.status)}",
        "",
        "پیام های اخیر:",
    ]
    for message in thread.messages[-6:]:
        sender = "ادمین" if message.sender_type == "admin" else "کاربر"
        body = " ".join((message.body or "").split())
        if len(body) > 260:
            body = f"{body[:257]}..."
        rows.append(f"- {sender}: {body}")
    return "\n".join(rows)


def _payment_request_text(payment_request) -> str:
    plan = payment_request.plan
    traffic = "نامحدود" if plan.data_limit_gb is None else f"{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("☑️ فاکتور شما با موفقیت ساخته شد"),
            f"🔖 شماره سفارش: {payment_request.order.id}",
            f"💳 شماره پرداخت: {payment_request.payment.id}",
            f"پلن انتخابی: {plan.name}",
            f"نام سرویس: {payment_request.order.requested_username or '-'}",
            f"💳 مبلغ قابل پرداخت: {payment_request.payment.amount:,.0f} تومان",
            f"مدت زمان: {plan.duration_days} روز",
            f"حجم: {traffic}",
            "",
            payment_request.instructions,
            "",
            "بعد از تایید پرداخت، سرویس شما ساخته یا بروزرسانی می‌شود.",
        ]
    )


def _buyer_order_status_text(order_status) -> str:
    order = order_status.order
    payment = order_status.payment
    plan = order_status.plan
    rows = [
        title("🔎 وضعیت سفارش"),
        f"شماره سفارش: {order.id}",
        f"نوع سفارش: {order.order_type}",
        f"وضعیت سفارش: {status_label(order.status)}",
        f"مبلغ: {order.total_amount:,.0f} تومان",
        f"پلن: {plan.name if plan else '-'}",
        f"نام سرویس: {order.requested_username or '-'}",
    ]
    if payment is not None:
        rows.extend(
            [
                "",
                f"شماره پرداخت: {payment.id}",
                f"وضعیت پرداخت: {status_label(payment.status)}",
                f"روش پرداخت: {payment.method}",
            ]
        )
    rows.extend(["", "پرداخت باید توسط ادمین تایید شود."])
    return "\n".join(rows)


def _receipt_upload_request_text(order_id: str) -> str:
    return "\n".join(
        [
            title("📤 ارسال فیش"),
            f"شماره سفارش: {order_id}",
            "",
            "عکس فیش پرداخت را همینجا داخل ربات ارسال کنید.",
            "ربات عکس را برای ادمین و پشتیبان می‌فرستد تا پرداخت تایید شود.",
        ]
    )


def _wallet_receipt_upload_request_text(transaction_id: str) -> str:
    return "\n".join(
        [
            title("📤 ارسال فیش شارژ کیف پول"),
            f"شماره تراکنش: {transaction_id}",
            "",
            "عکس فیش شارژ کیف پول را همینجا داخل ربات ارسال کنید.",
            "ربات عکس را برای ادمین و پشتیبان ارسال می‌کند.",
            "",
            "برای روش پرداخت دیگر، به پشتیبانی پیام بدهید.",
        ]
    )


def _receipt_notification_caption(*, buyer_telegram_id: int, order_status) -> str:
    order = order_status.order
    payment = order_status.payment
    plan = order_status.plan
    amount = payment.amount if payment is not None else order.total_amount
    return "\n".join(
        [
            title("فیش پرداخت جدید"),
            f"Telegram ID خریدار: {buyer_telegram_id}",
            f"کد سفارش: {order.id}",
            f"کد پرداخت: {payment.id if payment else '-'}",
            f"پلن: {plan.name if plan else '-'}",
            f"مبلغ: {amount:,.0f} تومان",
            f"وضعیت پرداخت: {status_label(payment.status) if payment else '-'}",
            "",
            "بعد از بررسی عکس، پرداخت را تایید یا رد کنید.",
        ]
    )


def _wallet_receipt_notification_caption(*, buyer_telegram_id: int, transaction) -> str:
    return "\n".join(
        [
            title("فیش شارژ کیف پول"),
            f"Telegram ID خریدار: {buyer_telegram_id}",
            f"کد تراکنش: {transaction.id}",
            f"مبلغ: {transaction.amount:,.0f} تومان",
            f"وضعیت: {status_label(transaction.status)}",
            "",
            "بعد از بررسی عکس، شارژ کیف پول را تایید کنید.",
        ]
    )


async def _send_receipt_to_contact(
    message: Message,
    *,
    chat_id: int | str,
    photo_file_id: str,
    caption: str,
    payment_id: str,
    include_actions: bool,
) -> None:
    try:
        await message.bot.send_photo(
            chat_id,
            photo_file_id,
            caption=caption,
            reply_markup=admin_payment_actions(payment_id) if include_actions else None,
        )
    except TelegramAPIError:
        return


async def _send_wallet_receipt_to_contact(
    message: Message,
    *,
    chat_id: int | str,
    photo_file_id: str,
    caption: str,
    transaction_id: str,
    include_actions: bool,
) -> None:
    try:
        await message.bot.send_photo(
            chat_id,
            photo_file_id,
            caption=caption,
            reply_markup=admin_wallet_charge_actions(transaction_id) if include_actions else None,
        )
    except TelegramAPIError:
        return


def _pending_payment_detail_text(pending) -> str:
    plan = pending.plan
    traffic = "نامحدود" if plan.data_limit_gb is None else f"{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("جزئیات پرداخت"),
            f"کد پرداخت: {pending.payment.id}",
            f"وضعیت پرداخت: {status_label(pending.payment.status)}",
            f"روش: {pending.payment.method}",
            f"مبلغ: {pending.payment.amount:,.0f}",
            "",
            f"کد سفارش: {pending.order.id}",
            f"نوع سفارش: {pending.order.order_type}",
            f"وضعیت سفارش: {status_label(pending.order.status)}",
            "",
            f"پلن: {plan.name}",
            f"مدت: {plan.duration_days} روز",
            f"حجم: {traffic}",
            "",
            "فقط بعد از بررسی فیش یا پیام پشتیبانی پرداخت را تایید کنید.",
        ]
    )


def _wallet_charge_confirm_text(amount: float) -> str:
    return "\n".join(
        [
            title("تایید شارژ کیف پول"),
            f"مبلغ شارژ: {amount:,.0f} تومان",
            "",
            "با تایید، درخواست شارژ کیف پول ساخته می‌شود.",
            "بعد از ساخت درخواست، عکس فیش را داخل ربات ارسال کنید.",
            "",
            "برای روش پرداخت دیگر، به پشتیبانی پیام بدهید.",
        ]
    )


def _wallet_charge_request_text(charge) -> str:
    return "\n".join(
        [
            title("درخواست شارژ کیف پول"),
            f"شماره تراکنش: {charge.transaction.id}",
            f"مبلغ: {charge.transaction.amount:,.0f} تومان",
            "",
            charge.instructions,
            "",
            "بعد از پرداخت، عکس فیش را با دکمه ارسال فیش بفرستید.",
            "برای روش پرداخت دیگر، به پشتیبانی پیام بدهید.",
        ]
    )


def _service_created_text(header: str, service) -> str:
    traffic = "نامحدود" if service.data_limit_gb is None else f"{service.data_limit_gb} گیگ"
    expire = service.expire_at.isoformat() if service.expire_at else "نامحدود"
    return "\n".join(
        [
            title(header),
            f"کد سرویس: {service.id}",
            f"نام کاربری: {service.marzban_username}",
            f"حجم: {traffic}",
            f"تاریخ انقضا: {expire}",
            f"لینک اشتراک: {service.subscription_url or '-'}",
        ]
    )


def _trial_error_text(error: str) -> str:
    messages = {
        "trial_disabled": "سرویس تستی فعلاً غیرفعال است.",
        "trial_already_used": "شما قبلاً سرویس تستی خود را استفاده کرده اید.",
        "panel_assignment_not_found": "سرویس تستی در دسترس نیست چون هیچ پنلی اختصاص داده نشده است.",
    }
    return "\n".join([title("سرویس تستی"), messages.get(error, "سرویس تستی فعلاً در دسترس نیست.")])


async def _show_admin_dashboard(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_payments(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    await callback.message.edit_text(
        "\n".join(
            [
                title("مدیریت فروشنده"),
                f"پرداخت های در انتظار: {len(pending)}",
                "",
                "یکی از عملیات مدیریت را انتخاب کنید.",
            ]
        ),
        reply_markup=seller_admin_menu(),
    )


async def _show_admin_payments(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_payments(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    rows = [
        f"- پرداخت={item.payment.id} | سفارش={short_id(item.order.id)} | {item.payment.amount:,.0f}"
        for item in pending[:15]
    ]
    rows.extend(["", "قبل از تایید پرداخت، جزئیات را بررسی کنید."])
    await callback.message.edit_text(
        "\n".join([title("پرداخت های در انتظار"), section("پرداخت ها", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in pending[:5]:
        await callback.message.answer(
            "\n".join(
                [
                    title("عملیات پرداخت"),
                    f"کد پرداخت: {item.payment.id}",
                    f"کد سفارش: {item.order.id}",
                    f"پلن: {item.plan.name}",
                    f"مبلغ: {item.payment.amount:,.0f}",
                ]
            ),
            reply_markup=admin_payment_actions(item.payment.id),
        )


async def _show_admin_payment_settings(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        config = await seller_context.get_crypto_payment_config(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    await callback.message.edit_text(
        _crypto_payment_settings_text(config),
        reply_markup=admin_payment_settings_menu(has_crypto=config is not None),
    )


async def _show_admin_support_settings(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        settings = await seller_context.get_support_settings(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    await callback.message.edit_text(
        _support_settings_text(settings),
        reply_markup=admin_support_settings_menu(has_support=settings.contact is not None),
    )


def _support_settings_text(settings: object) -> str:
    contact = getattr(settings, "contact", None)
    if contact is None:
        return "\n".join(
            [
                title("پشتیبان"),
                "هنوز پشتیبان تنظیم نشده است.",
                "",
                "می‌توانید Telegram ID، یوزرنیم، یا پیام فوروارد شده از پشتیبان را ثبت کنید.",
            ]
        )
    return "\n".join(
        [
            title("پشتیبان"),
            f"راه ارتباطی: {contact}",
            "",
            "تیکت‌های جدید و پاسخ‌های کاربر برای این راه ارتباطی ارسال می‌شود.",
        ]
    )


async def _support_contact_line(
    seller_context: SellerContextService,
    *,
    buyer_telegram_id: int,
) -> str:
    support_contact = await seller_context.get_support_contact_for_buyer(
        buyer_telegram_id=buyer_telegram_id,
    )
    if support_contact is None:
        return "پشتیبان هنوز توسط ادمین تنظیم نشده است."
    return f"پشتیبان: {support_contact}"


async def _edit_or_answer_callback(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup=None,
) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramAPIError:
        await callback.message.answer(text, reply_markup=reply_markup)


def _marzban_http_error_text(exc: httpx.HTTPStatusError) -> str:
    body = exc.response.text.strip()
    if len(body) > 160:
        body = f"{body[:157]}..."
    return f"خطای مرزبان {exc.response.status_code}: {body or exc.response.reason_phrase}"


def _normalize_service_username(value: str) -> str | None:
    username = value.strip().lower()
    if username.startswith("@"):
        username = username[1:]
    if not 3 <= len(username) <= 25:
        return None
    if re.fullmatch(r"[a-z0-9_]+", username) is None:
        return None
    if username.startswith("_") or username.endswith("_") or "__" in username:
        return None
    return username


def _extract_support_contact_from_message(message: Message) -> str | None:
    text = (message.text or "").strip()
    if text:
        return text
    forward_from = getattr(message, "forward_from", None)
    if forward_from is not None and getattr(forward_from, "id", None):
        return str(forward_from.id)
    forward_from_chat = getattr(message, "forward_from_chat", None)
    if forward_from_chat is not None:
        chat_id = getattr(forward_from_chat, "id", None)
        username = getattr(forward_from_chat, "username", None)
        if username:
            return f"@{username}"
        if chat_id:
            return str(chat_id)
    forward_origin = getattr(message, "forward_origin", None)
    sender_user = getattr(forward_origin, "sender_user", None)
    if sender_user is not None and getattr(sender_user, "id", None):
        return str(sender_user.id)
    chat = getattr(forward_origin, "chat", None)
    if chat is not None:
        username = getattr(chat, "username", None)
        chat_id = getattr(chat, "id", None)
        if username:
            return f"@{username}"
        if chat_id:
            return str(chat_id)
    return None


async def _notify_support_about_ticket(
    message: Message,
    seller_context: SellerContextService,
    *,
    buyer_telegram_id: int,
    header: str,
    ticket_id: str,
    subject: str,
    body: str,
) -> None:
    support_contact = await seller_context.get_support_contact_for_buyer(
        buyer_telegram_id=buyer_telegram_id,
    )
    if support_contact is None or support_contact == buyer_telegram_id:
        return
    preview = " ".join(body.split())
    if len(preview) > 900:
        preview = f"{preview[:897]}..."
    text = "\n".join(
        [
            title(header),
            f"کد تیکت: {ticket_id}",
            f"Telegram ID خریدار: {buyer_telegram_id}",
            f"موضوع: {subject}",
            "",
            preview,
            "",
            "برای پاسخ، وارد پنل مدیریت همین ربات شوید و تیکت را باز کنید.",
        ]
    )
    try:
        await message.bot.send_message(support_contact, text)
    except TelegramAPIError:
        return


def _crypto_payment_settings_text(config: object | None) -> str:
    if config is None:
        return "\n".join(
            [
                title("روش پرداخت"),
                "هنوز روش پرداخت ارز دیجیتال برای این ربات تنظیم نشده است.",
                "",
                "بعد از ساخت، کاربران هنگام خرید اطلاعات ولت را می‌بینند.",
            ]
        )
    currency = str(getattr(config, "currency"))
    network = str(getattr(config, "network"))
    wallet_address = str(getattr(config, "wallet_address"))
    note = getattr(config, "note", None)
    lines = [
        title("روش پرداخت ارز دیجیتال"),
        f"ارز: {currency}",
        f"شبکه: {network}",
        "",
        "آدرس ولت:",
        wallet_address,
    ]
    if note:
        lines.extend(["", f"توضیح: {note}"])
    return "\n".join(lines)


def _crypto_payment_confirm_text(spec: dict[str, object]) -> str:
    lines = [
        title("تایید روش پرداخت"),
        f"ارز: {spec.get('currency')}",
        f"شبکه: {spec.get('network')}",
        "",
        "آدرس ولت:",
        str(spec.get("wallet_address") or ""),
    ]
    note = str(spec.get("note") or "").strip()
    if note:
        lines.extend(["", f"توضیح: {note}"])
    lines.extend(["", "این اطلاعات برای پرداخت‌های جدید کاربران نمایش داده می‌شود."])
    return "\n".join(lines)


async def _send_admin_payments(message: Message, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_payments(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    rows = [
        f"- پرداخت={item.payment.id} | سفارش={short_id(item.order.id)} | {item.payment.amount:,.0f}"
        for item in pending[:15]
    ]
    rows.extend(["", "قبل از تایید پرداخت، جزئیات را بررسی کنید."])
    await message.answer(
        "\n".join([title("پرداخت های در انتظار"), section("پرداخت ها", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in pending[:5]:
        await message.answer(
            "\n".join(
                [
                    title("عملیات پرداخت"),
                    f"کد پرداخت: {item.payment.id}",
                    f"کد سفارش: {item.order.id}",
                    f"پلن: {item.plan.name}",
                    f"مبلغ: {item.payment.amount:,.0f}",
                ]
            ),
            reply_markup=admin_payment_actions(item.payment.id),
        )


async def _show_admin_orders(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        orders = await seller_context.list_provisioning_orders(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    rows = [_admin_order_row(item) for item in orders[:15]]
    rows.extend(["", "سفارش های تایید شده آماده ساخت، تمدید یا افزایش حجم هستند."])
    await callback.message.edit_text(
        "\n".join([title("سفارش های آماده"), section("سفارش ها", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in orders[:5]:
        is_renewal = item.order.order_type == OrderType.RENEWAL.value
        is_extra_volume = item.order.order_type == OrderType.EXTRA_VOLUME.value
        await callback.message.answer(
            _admin_order_card_text(item),
            reply_markup=admin_order_actions(item.order.id, renewal=is_renewal, extra_volume=is_extra_volume),
        )


async def _send_admin_orders(message: Message, seller_context: SellerContextService) -> None:
    try:
        orders = await seller_context.list_provisioning_orders(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    rows = [_admin_order_row(item) for item in orders[:15]]
    rows.extend(["", "سفارش های تایید شده آماده ساخت، تمدید یا افزایش حجم هستند."])
    await message.answer(
        "\n".join([title("سفارش های آماده"), section("سفارش ها", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in orders[:5]:
        is_renewal = item.order.order_type == OrderType.RENEWAL.value
        is_extra_volume = item.order.order_type == OrderType.EXTRA_VOLUME.value
        await message.answer(
            _admin_order_card_text(item),
            reply_markup=admin_order_actions(item.order.id, renewal=is_renewal, extra_volume=is_extra_volume),
        )


async def _show_admin_wallet(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_wallet_charges(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    rows = [f"- تراکنش={item.id} | مبلغ={item.amount:,.0f}" for item in pending[:15]]
    rows.extend(["", "برای تایید، از کارت شارژ کیف پول زیر استفاده کنید."])
    await callback.message.edit_text(
        "\n".join([title("شارژهای کیف پول"), section("شارژهای در انتظار", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in pending[:5]:
        await callback.message.answer(
            "\n".join(
                [
                    title("عملیات شارژ کیف پول"),
                    f"کد تراکنش: {item.id}",
                    f"کد خریدار: {item.owner_id}",
                    f"مبلغ: {item.amount:,.0f}",
                ]
            ),
            reply_markup=admin_wallet_charge_actions(item.id),
        )


async def _send_admin_wallet(message: Message, seller_context: SellerContextService) -> None:
    try:
        pending = await seller_context.list_pending_wallet_charges(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    rows = [f"- تراکنش={item.id} | مبلغ={item.amount:,.0f}" for item in pending[:15]]
    rows.extend(["", "برای تایید، از کارت شارژ کیف پول زیر استفاده کنید."])
    await message.answer(
        "\n".join([title("شارژهای کیف پول"), section("شارژهای در انتظار", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in pending[:5]:
        await message.answer(
            "\n".join(
                [
                    title("عملیات شارژ کیف پول"),
                    f"کد تراکنش: {item.id}",
                    f"کد خریدار: {item.owner_id}",
                    f"مبلغ: {item.amount:,.0f}",
                ]
            ),
            reply_markup=admin_wallet_charge_actions(item.id),
        )


async def _show_admin_customers(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        customers = await seller_context.list_customers(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    await callback.message.edit_text(
        _admin_customers_text(customers),
        reply_markup=admin_customers_menu(),
    )
    for item in customers[:8]:
        await callback.message.answer(
            _admin_customer_card_text(item),
            reply_markup=admin_customer_card_actions(item.buyer.id),
        )


async def _send_admin_customers(message: Message, seller_context: SellerContextService) -> None:
    try:
        customers = await seller_context.list_customers(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    await message.answer(
        _admin_customers_text(customers),
        reply_markup=admin_customers_menu(),
    )
    for item in customers[:8]:
        await message.answer(
            _admin_customer_card_text(item),
            reply_markup=admin_customer_card_actions(item.buyer.id),
        )


async def _show_admin_plans(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        plans = await seller_context.list_admin_plans(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    await callback.message.edit_text(_admin_plans_text(plans), reply_markup=admin_plan_list_menu(plans))


async def _send_admin_plans(message: Message, seller_context: SellerContextService) -> None:
    try:
        plans = await seller_context.list_admin_plans(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    await message.answer(_admin_plans_text(plans), reply_markup=admin_plan_list_menu(plans))


def _admin_order_row(item) -> str:
    return (
        f"- سفارش={short_id(item.order.id)} | {item.order.order_type} | "
        f"پلن={item.plan.name} | مبلغ={item.order.total_amount:,.0f}"
    )


def _admin_order_card_text(item) -> str:
    return "\n".join(
        [
            title("سفارش آماده ساخت"),
            f"کد سفارش: {item.order.id}",
            f"نوع: {item.order.order_type}",
            f"وضعیت: {status_label(item.order.status)}",
            f"Telegram ID خریدار: {item.buyer.telegram_user_id}",
            f"پلن: {item.plan.name}",
            f"مبلغ: {item.order.total_amount:,.0f}",
        ]
    )


def _admin_customer_row(item) -> str:
    user = item.telegram_user
    username = f"@{user.username}" if user.username else "-"
    name = " ".join(part for part in [user.first_name, user.last_name] if part) or "-"
    return (
        f"- تلگرام={user.id} | {username} | {name} | "
        f"کیف پول={item.buyer.wallet_balance:,.0f} | کد={short_id(item.buyer.id)}"
    )


def _admin_customer_card_text(item) -> str:
    user = item.telegram_user
    username = f"@{user.username}" if user.username else "-"
    name = " ".join(part for part in [user.first_name, user.last_name] if part) or "-"
    return "\n".join(
        [
            title("کاربر"),
            f"کد خریدار: {item.buyer.id}",
            f"Telegram ID: {user.id}",
            f"یوزرنیم: {username}",
            f"نام: {name}",
            f"کیف پول: {item.buyer.wallet_balance:,.0f}",
        ]
    )


def _admin_customers_text(customers, *, heading: str = "کاربران") -> str:
    if not customers:
        return "\n".join([title(heading), "کاربری پیدا نشد.", "", "برای جستجو از Telegram ID، یوزرنیم، نام یا نام VPN استفاده کنید."])
    rows = [_admin_customer_row(item) for item in customers[:20]]
    rows.extend(["", "برای مشاهده جزئیات، روی کارت کاربر بزنید."])
    return "\n".join([title(heading), section("کاربران اخیر", rows)])


def _admin_customer_detail_text(detail) -> str:
    user = detail.telegram_user
    username = f"@{user.username}" if user.username else "-"
    name = " ".join(part for part in [user.first_name, user.last_name] if part) or "-"
    return "\n".join(
        [
            title("جزئیات کاربر"),
            f"کد خریدار: {detail.buyer.id}",
            f"Telegram ID: {user.id}",
            f"یوزرنیم: {username}",
            f"نام: {name}",
            f"کیف پول: {detail.buyer.wallet_balance:,.0f}",
            "",
            f"سرویس ها: {detail.service_count}",
            f"سفارش ها: {detail.order_count}",
            f"تیکت ها: {detail.ticket_count}",
        ]
    )


def _admin_plans_text(plans) -> str:
    rows = []
    for plan in plans[:20]:
        traffic = "نامحدود" if plan.data_limit_gb is None else f"{plan.data_limit_gb} گیگ"
        owner = "اختصاصی" if plan.reseller_id else "عمومی"
        rows.append(
            f"▫️ {plan.name} | {owner} | {plan.price:,.0f} تومان | {plan.duration_days} روز | {traffic} | کد: {short_id(plan.id)}"
        )
    if not rows:
        rows.append("هنوز پلن اختصاصی برای این فروشنده ساخته نشده است.")
    rows.extend(["", "یکی از دکمه‌های پلن را انتخاب کنید تا مدیریت همان پلن باز شود."])
    return "\n".join([title("🛒 تعرفه خدمات"), section("پلن های فعال", rows)])


def _find_admin_plan(plans, *, plan_id: str):
    return next((plan for plan in plans if plan.id == plan_id), None)


def _admin_plan_card_text(plan) -> str:
    traffic = f"{plan.data_limit_gb} گیگ" if plan.data_limit_gb is not None else "-"
    owner = "اختصاصی" if plan.reseller_id else "عمومی"
    note = "برای تغییر این پلن از دکمه‌های زیر استفاده کنید." if plan.reseller_id else "این پلن عمومی است و از ربات سلر قابل ویرایش نیست."
    return "\n".join(
        [
            title("مدیریت پلن"),
            f"نام: {plan.name}",
            f"نوع: {owner}",
            f"قیمت: {plan.price:,.0f} تومان",
            f"مدت: {plan.duration_days} روز",
            f"حجم: {traffic}",
            f"کد: {short_id(plan.id)}",
            "",
            note,
        ]
    )


def _parse_positive_int(raw: str | None) -> int | None:
    try:
        value = int((raw or "").strip().replace(",", ""))
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _parse_positive_float(raw: str | None) -> float | None:
    try:
        value = float((raw or "").strip().replace(",", ""))
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _admin_plan_confirm_text(spec: dict, *, edited: bool = False) -> str:
    traffic = f"{spec['data_limit_gb']} گیگ"
    return "\n".join(
        [
            title("تایید ویرایش پلن" if edited else "تایید پلن فروش"),
            f"نام: {spec['name']}",
            f"قیمت: {spec['price']:,.0f} تومان",
            f"مدت: {spec['duration_days']} روز",
            f"حجم: {traffic}",
            "",
            "اگر اطلاعات درست است تایید را بزنید.",
        ]
    )


def _admin_plan_saved_text(plan, *, edited: bool = False) -> str:
    traffic = f"{plan.data_limit_gb} گیگ"
    return "\n".join(
        [
            title("پلن فروش ویرایش شد" if edited else "پلن فروش ساخته شد"),
            f"نام: {plan.name}",
            f"قیمت: {plan.price:,.0f} تومان",
            f"مدت: {plan.duration_days} روز",
            f"حجم: {traffic}",
            "",
            "این پلن برای خریداران به صورت دکمه نمایش داده می‌شود.",
        ]
    )


async def _show_admin_tickets(callback: CallbackQuery, seller_context: SellerContextService) -> None:
    try:
        tickets = await seller_context.list_open_tickets(admin_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("شما دسترسی ادمین فروشنده ندارید.", show_alert=True)
        return
    rows = [f"- تیکت={item.id} | {item.subject}" for item in tickets[:15]]
    rows.extend(["", "برای بستن یا پاسخ، از کارت تیکت زیر استفاده کنید."])
    await callback.message.edit_text(
        "\n".join([title("تیکت های باز"), section("تیکت ها", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in tickets[:5]:
        await callback.message.answer(
            "\n".join(
                [
                    title("عملیات تیکت"),
                    f"کد تیکت: {item.id}",
                    f"موضوع: {item.subject}",
                    f"وضعیت: {status_label(item.status)}",
                ]
            ),
            reply_markup=admin_ticket_actions(item.id),
        )


async def _send_admin_tickets(message: Message, seller_context: SellerContextService) -> None:
    try:
        tickets = await seller_context.list_open_tickets(admin_telegram_id=message.from_user.id)
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    rows = [f"- تیکت={item.id} | {item.subject}" for item in tickets[:15]]
    rows.extend(["", "برای بستن یا پاسخ، از کارت تیکت زیر استفاده کنید."])
    await message.answer(
        "\n".join([title("تیکت های باز"), section("تیکت ها", rows)]),
        reply_markup=seller_admin_menu(),
    )
    for item in tickets[:5]:
        await message.answer(
            "\n".join(
                [
                    title("عملیات تیکت"),
                    f"کد تیکت: {item.id}",
                    f"موضوع: {item.subject}",
                    f"وضعیت: {status_label(item.status)}",
                ]
            ),
            reply_markup=admin_ticket_actions(item.id),
        )


def _format_report(title: str, report: dict[str, float | int]) -> str:
    labels = {
        "completed_orders": "سفارش های تکمیل شده",
        "total_revenue": "درآمد کل",
        "new_services": "سرویس های جدید",
        "renewals": "تمدیدها",
        "extra_volume": "حجم اضافه",
        "buyers": "خریداران",
        "resellers": "فروشنده ها",
        "payments": "پرداخت ها",
    }
    lines = [title]
    for key, value in report.items():
        label = labels.get(key, key.replace("_", " "))
        if isinstance(value, float):
            lines.append(f"{label}: {value:,.0f}")
        else:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _guided_text(name: str, description: str, examples: list[str]) -> str:
    rows = [title(name), description]
    if examples:
        rows.extend(["", "وقتی متن لازم است، یک پیام با این فرمت بفرستید:", *[f"- {item}" for item in examples]])
    return "\n".join(rows)


@router.message(Command("apply_renewal"))
async def apply_renewal(
    message: Message,
    command: CommandObject,
    provisioning_service: ProvisioningService,
) -> None:
    if message.from_user is None:
        return
    order_id = (command.args or "").strip()
    if not order_id:
        await message.answer("فرمت دستور: /apply_renewal <order_id>")
        return
    try:
        renewed = await provisioning_service.apply_renewal(
            admin_telegram_id=message.from_user.id,
            order_id=order_id,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    except ValueError as exc:
        if str(exc) == "renewal_not_ready":
            await message.answer("سفارش تمدید آماده نیست.")
            return
        if str(exc) == "panel_not_found":
            await message.answer("پنل این سرویس در دسترس نیست.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "سرویس VPN تمدید شد.",
                f"کد سفارش: {renewed.order.id}",
                f"کد سرویس: {renewed.vpn_service.id}",
                f"نام کاربری: {renewed.vpn_service.marzban_username}",
                f"انقضای جدید: {renewed.vpn_service.expire_at.isoformat() if renewed.vpn_service.expire_at else 'نامحدود'}",
            ]
        )
    )


@router.message(Command("apply_extra_volume"))
async def apply_extra_volume(
    message: Message,
    command: CommandObject,
    provisioning_service: ProvisioningService,
) -> None:
    if message.from_user is None:
        return
    order_id = (command.args or "").strip()
    if not order_id:
        await message.answer("فرمت دستور: /apply_extra_volume <order_id>")
        return
    try:
        applied = await provisioning_service.apply_extra_volume(
            admin_telegram_id=message.from_user.id,
            order_id=order_id,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    except ValueError as exc:
        if str(exc) == "extra_volume_not_ready":
            await message.answer("سفارش حجم اضافه آماده نیست.")
            return
        if str(exc) == "panel_not_found":
            await message.answer("پنل این سرویس در دسترس نیست.")
            return
        raise
    await message.answer(
        "\n".join(
            [
                "حجم اضافه اعمال شد.",
                f"کد سفارش: {applied.order.id}",
                f"کد سرویس: {applied.vpn_service.id}",
                f"نام کاربری: {applied.vpn_service.marzban_username}",
                f"حجم جدید: {'نامحدود' if applied.vpn_service.data_limit_gb is None else f'{applied.vpn_service.data_limit_gb} گیگ'}",
            ]
        )
    )


@router.message(Command("provision_order"))
async def provision_order(
    message: Message,
    command: CommandObject,
    provisioning_service: ProvisioningService,
) -> None:
    if message.from_user is None:
        return
    order_id = (command.args or "").strip()
    if not order_id:
        await message.answer("فرمت دستور: /provision_order <order_id>")
        return
    try:
        provisioned = await provisioning_service.provision_order(
            admin_telegram_id=message.from_user.id,
            order_id=order_id,
        )
    except PermissionError:
        await message.answer("شما دسترسی ادمین فروشنده ندارید.")
        return
    except ValueError as exc:
        if str(exc) == "order_not_ready":
            await message.answer("سفارش برای ساخت سرویس آماده نیست.")
            return
        if str(exc) == "order_already_completed_without_service_link":
            await message.answer("سفارش تکمیل شده اما لینک سرویس آن ثبت نشده است. از سوپر ادمین بخواهید آن را اصلاح کند.")
            return
        if str(exc) == "panel_assignment_not_found":
            await message.answer("هیچ پنل مرزبان فعالی به این فروشنده اختصاص داده نشده است.")
            return
        raise

    subscription_url = provisioned.vpn_service.subscription_url
    text = "\n".join(
        [
            "سرویس VPN ساخته شد.",
            f"کد سفارش: {provisioned.order.id}",
            f"کد سرویس: {provisioned.vpn_service.id}",
            f"نام کاربری: {provisioned.vpn_service.marzban_username}",
            f"لینک اشتراک: {subscription_url or '-'}",
        ]
    )
    if not subscription_url:
        await message.answer(text)
        return

    qr_file = BufferedInputFile(
        make_qr_png_bytes(subscription_url),
        filename=f"{provisioned.vpn_service.marzban_username}.png",
    )
    await message.answer_photo(qr_file, caption=text)


async def _blocked_by_forced_join(message: Message) -> bool:
    if message.from_user is None:
        return True
    missing = await missing_required_chats(message.bot, user_id=message.from_user.id)
    if not missing:
        return False
    lines = ["لطفاً ابتدا عضو کانال یا گروه الزامی شوید:"]
    for chat in missing:
        lines.append(f"- {chat.title or chat.chat_id}")
    lines.extend(["", "بعد از عضویت، دکمه «عضو شدم» را بزنید."])
    await message.answer("\n".join(lines), reply_markup=forced_join_blocked_menu())
    return True
