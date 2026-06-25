from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from vpn_bot_platform.common.ui.callbacks import build_callback


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=callback_data) for text, callback_data in row]
            for row in rows
        ]
    )


@dataclass(frozen=True)
class Page:
    items: list[object]
    page: int
    total_pages: int
    total_items: int


def paginate(items: list[object], *, page: int = 1, per_page: int = 10) -> Page:
    if per_page < 1:
        raise ValueError("per_page_must_be_positive")
    total_items = len(items)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    safe_page = min(max(page, 1), total_pages)
    start = (safe_page - 1) * per_page
    return Page(
        items=items[start : start + per_page],
        page=safe_page,
        total_pages=total_pages,
        total_items=total_items,
    )


def pagination_row(
    *,
    scope: str,
    action: str,
    page: int,
    total_pages: int,
) -> list[tuple[str, str]]:
    if total_pages <= 1:
        return []
    previous_page = max(1, page - 1)
    next_page = min(total_pages, page + 1)
    return [
        ("قبلی", build_callback(scope, action, str(previous_page))),
        (f"{page}/{total_pages}", build_callback(scope, action, str(page))),
        ("بعدی", build_callback(scope, action, str(next_page))),
    ]


def nav_row(
    *,
    scope: str,
    home_action: str = "home",
    back_action: str | None = None,
    refresh_action: str | None = None,
    cancel_action: str | None = None,
) -> list[tuple[str, str]]:
    row: list[tuple[str, str]] = []
    if back_action:
        row.append(("🔙 بازگشت", build_callback(scope, back_action)))
    if refresh_action:
        row.append(("🔄 بروزرسانی", build_callback(scope, refresh_action)))
    if cancel_action:
        row.append(("❌ انصراف", build_callback(scope, cancel_action)))
    row.append(("📱 منوی اصلی", build_callback(scope, home_action)))
    return row


def confirm_keyboard(
    *,
    scope: str,
    confirm_action: str,
    cancel_action: str,
    value: str | None = None,
) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("✅ تایید", build_callback(scope, confirm_action, value)),
                ("❌ لغو", build_callback(scope, cancel_action, value)),
            ]
        ]
    )


def cancel_only_keyboard(*, scope: str, cancel_action: str) -> InlineKeyboardMarkup:
    return inline_keyboard([[("❌ انصراف", build_callback(scope, cancel_action))]])


def reply_keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
    )


def master_reply_menu() -> ReplyKeyboardMarkup:
    return reply_keyboard(
        [
            ["ربات های فروشنده", "افزودن ربات فروشنده"],
        ]
    )


def master_main_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [("🤖 ربات های فروشنده", build_callback("m", "seller_bots"))],
            [("➕ افزودن ربات فروشنده", build_callback("m", "add_seller_bot"))],
            [
                ("⚙️ تنظیمات پلتفرم", build_callback("m", "platform_settings")),
                ("📊 گزارش ها", build_callback("m", "reports")),
            ],
        ]
    )


def master_section_menu(section: str) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    if section == "resellers":
        rows.append(
            [
                ("تغییر نام", build_callback("m", "guide_rename_reseller")),
            ]
        )
    elif section == "seller_bots":
        rows.append(
            [
                ("➕ افزودن ربات فروشنده", build_callback("m", "add_seller_bot")),
                ("🔎 جستجو", build_callback("m", "seller_search")),
            ]
        )
        rows.append([("🧩 قالب های ربات", build_callback("m", "external_bots"))])
    elif section == "platform_settings":
        rows.append(
            [
                ("فروشنده ها", build_callback("m", "resellers")),
                ("پنل ها", build_callback("m", "panels")),
            ]
        )
        rows.append(
            [
                ("پلن ها", build_callback("m", "plans")),
                ("کدهای تخفیف", build_callback("m", "discounts")),
            ]
        )
        rows.append(
            [
                ("پیام های همگانی", build_callback("m", "broadcasts")),
                ("سیستم", build_callback("m", "system")),
            ]
        )
    elif section == "external_bots":
        rows.append(
            [
                ("افزودن قالب", build_callback("m", "guide_add_external_template")),
                ("افزودن ربات خارجی", build_callback("m", "guide_add_external_seller_bot")),
            ]
        )
    elif section == "panels":
        rows.append([("اختصاص پنل", build_callback("m", "guide_assign_panel"))])
    elif section == "plans":
        rows.append(
            [
                ("افزودن پلن عمومی", build_callback("m", "guide_add_global_plan")),
                ("افزودن پلن فروشنده", build_callback("m", "guide_add_reseller_plan")),
            ]
        )
    elif section == "discounts":
        rows.append([("افزودن تخفیف", build_callback("m", "guide_add_discount"))])
    elif section == "broadcasts":
        rows.append(
            [
                ("ساخت پیام همگانی", build_callback("m", "guide_global_broadcast")),
                ("پیش نویس ها", build_callback("m", "broadcast_history")),
            ]
        )
    elif section == "settings":
        rows.append(
            [
                ("عضویت اجباری", build_callback("m", "settings_forced_join")),
                ("محدودیت درخواست", build_callback("m", "settings_rate_limits")),
            ]
        )
        rows.append(
            [
                ("تست رایگان", build_callback("m", "settings_trial")),
                ("پرداخت ها", build_callback("m", "settings_payments")),
            ]
        )
    elif section == "reports":
        rows.append(
            [
                ("امروز", build_callback("m", "report_1")),
                ("۷ روز", build_callback("m", "report_7")),
                ("۳۰ روز", build_callback("m", "report_30")),
            ]
        )
        rows.append([("بازه دلخواه", build_callback("m", "report_custom"))])
    elif section == "system":
        rows.append([("تنظیمات پیشرفته", build_callback("m", "settings"))])
        rows.append(
            [
                ("سلامت سیستم", build_callback("m", "system_health")),
                ("نسخه", build_callback("m", "system_version")),
            ]
        )
        rows.append(
            [
                ("بکاپ", build_callback("m", "system_backup")),
                ("لاگ بررسی", build_callback("m", "system_audit")),
            ]
        )
        rows.append([("خطاهای اخیر", build_callback("m", "system_errors"))])
    rows.append(
        nav_row(scope="m", refresh_action=section, home_action="home")
    )
    return inline_keyboard(rows)


def reseller_actions(telegram_id: int) -> InlineKeyboardMarkup:
    value = str(telegram_id)
    return inline_keyboard(
        [
            [
                ("فعال سازی", build_callback("m", "reseller_active", value)),
                ("تعلیق", build_callback("m", "reseller_suspended", value)),
            ],
            [
                ("غیرفعال", build_callback("m", "reseller_disabled", value)),
                ("انصراف", build_callback("m", "resellers")),
                ("خانه", build_callback("m", "home")),
            ],
        ]
    )


def external_template_actions(template_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("همگام سازی", build_callback("m", "ext_sync", template_id)),
                ("ربات های خارجی", build_callback("m", "external_bots")),
            ],
            nav_row(scope="m", back_action="seller_bots", home_action="home"),
        ]
    )


def seller_bot_list_menu(
    *,
    page: int,
    total_pages: int,
    seller_bots: list[object] | None = None,
    labels: dict[str, str] | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = [
        [
            ("➕ افزودن ربات فروشنده", build_callback("m", "add_seller_bot")),
            ("🔎 جستجو", build_callback("m", "seller_search")),
        ]
    ]
    for seller_bot in seller_bots or []:
        bot_id = str(getattr(seller_bot, "id"))
        name = str(getattr(seller_bot, "name", "ربات فروشنده")).strip() or "ربات فروشنده"
        status = str(getattr(seller_bot, "status", "")).strip()
        if labels and bot_id in labels:
            label = labels[bot_id]
        elif status:
            label = f"{name[:20]} | {status[:10]}"
        else:
            label = name[:32]
        rows.append([(label, build_callback("m", "seller_select", bot_id))])
    page_row = pagination_row(scope="m", action="seller_bots", page=page, total_pages=total_pages)
    if page_row:
        rows.append(page_row)
    rows.append(nav_row(scope="m", refresh_action="seller_bots", home_action="home"))
    return inline_keyboard(rows)


def seller_bot_provision_success_menu(*, seller_bot_id: str, panel_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Start bot", build_callback("m", "seller_start", seller_bot_id)),
                ("Test panel", build_callback("m", "panel_test", panel_id)),
            ],
            [
                ("Open bot config", build_callback("m", "seller_select", seller_bot_id)),
                ("Seller bots", build_callback("m", "seller_bots")),
            ],
            [("Home", build_callback("m", "home"))],
        ]
    )


def seller_bot_config_menu(seller_bot_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🧩 تنظیمات", build_callback("m", "seller_detail", seller_bot_id)),
                ("📡 پنل ربات", build_callback("m", "seller_config_panel", seller_bot_id)),
            ],
            [
                ("💰 قوانین قیمت گذاری", build_callback("m", "seller_config_pricing", seller_bot_id)),
                ("👥 ادمین های ربات", build_callback("m", "seller_config_admins", seller_bot_id)),
            ],
            [
                ("➕ افزودن گیگ", build_callback("m", "seller_volume_add", seller_bot_id)),
                ("📊 تنظیم سقف گیگ", build_callback("m", "seller_volume_edit", seller_bot_id)),
            ],
            [
                ("شروع", build_callback("m", "seller_start", seller_bot_id)),
                ("توقف", build_callback("m", "seller_stop", seller_bot_id)),
                ("راه اندازی مجدد", build_callback("m", "seller_restart", seller_bot_id)),
            ],
            [
                ("سلامت", build_callback("m", "seller_health", seller_bot_id)),
                ("لاگ ها", build_callback("m", "seller_logs", seller_bot_id)),
            ],
            [
                ("غیرفعال", build_callback("m", "seller_disable", seller_bot_id)),
                ("حذف", build_callback("m", "seller_delete_confirm", seller_bot_id)),
            ],
            [("بازگشت", build_callback("m", "seller_bots")), ("خانه", build_callback("m", "home"))],
        ]
    )


def seller_bot_type_menu(*, has_external_templates: bool) -> InlineKeyboardMarkup:
    rows = [[("ربات فروشنده داخلی", build_callback("m", "sellerbot_type", "native"))]]
    rows.append([("Simple Seller", build_callback("m", "sellerbot_type", "simple_seller"))])
    if has_external_templates:
        rows.append([("ربات با قالب خارجی", build_callback("m", "sellerbot_type", "external"))])
    rows.append([("انصراف", build_callback("m", "sellerbot_cancel")), ("خانه", build_callback("m", "home"))])
    return inline_keyboard(rows)


def reseller_card_actions(telegram_id: int) -> InlineKeyboardMarkup:
    value = str(telegram_id)
    return inline_keyboard(
        [
            [("جزئیات", build_callback("m", "reseller_detail", value))],
            [
                ("تغییر نام", build_callback("m", "reseller_rename_select", value)),
            ],
            [
                ("فعال سازی", build_callback("m", "reseller_active", value)),
                ("تعلیق", build_callback("m", "reseller_suspended", value)),
                ("غیرفعال", build_callback("m", "reseller_disabled", value)),
            ],
            [("بازگشت", build_callback("m", "resellers")), ("خانه", build_callback("m", "home"))],
        ]
    )


def reseller_detail_actions(telegram_id: int) -> InlineKeyboardMarkup:
    value = str(telegram_id)
    return inline_keyboard(
        [
            [
                ("ربات های فروشنده", build_callback("m", "reseller_seller_bots", value)),
                ("پلن ها", build_callback("m", "reseller_plans", value)),
            ],
            [("پنل های اختصاص داده شده", build_callback("m", "reseller_panels", value))],
            [
                ("تغییر نام", build_callback("m", "reseller_rename_select", value)),
                ("وضعیت", build_callback("m", "reseller_status_menu", value)),
            ],
            [("بازگشت", build_callback("m", "resellers")), ("خانه", build_callback("m", "home"))],
        ]
    )


def reseller_list_menu(*, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = [
        [
            ("افزودن فروشنده", build_callback("m", "guide_add_reseller")),
            ("تغییر نام", build_callback("m", "guide_rename_reseller")),
        ]
    ]
    page_row = pagination_row(scope="m", action="resellers", page=page, total_pages=total_pages)
    if page_row:
        rows.append(page_row)
    rows.append(nav_row(scope="m", refresh_action="resellers", home_action="home"))
    return inline_keyboard(rows)


def panel_actions(panel_id: str, *, auth_type: str = "password") -> InlineKeyboardMarkup:
    credential_action = (
        ("تغییر توکن", build_callback("m", "panel_change_token", panel_id))
        if auth_type == "token"
        else ("تغییر رمز", build_callback("m", "panel_change_password", panel_id))
    )
    return inline_keyboard(
        [
            [("جزئیات", build_callback("m", "panel_detail", panel_id))],
            [
                ("تست اتصال", build_callback("m", "panel_test", panel_id)),
                ("غیرفعال", build_callback("m", "panel_disable_confirm", panel_id)),
            ],
            [credential_action],
            [("اختصاص به فروشنده", build_callback("m", "guide_assign_panel"))],
            [("بازگشت", build_callback("m", "panels")), ("خانه", build_callback("m", "home"))],
        ]
    )


def plan_actions(plan_id: str, *, is_active: bool = True) -> InlineKeyboardMarkup:
    toggle_label = "غیرفعال" if is_active else "فعال"
    toggle_action = "plan_disable_confirm" if is_active else "plan_enable"
    return inline_keyboard(
        [
            [("جزئیات", build_callback("m", "plan_detail", plan_id))],
            [(toggle_label, build_callback("m", toggle_action, plan_id))],
            [("بازگشت", build_callback("m", "plans")), ("خانه", build_callback("m", "home"))],
        ]
    )


def discount_actions(discount_id: str, *, is_active: bool = True) -> InlineKeyboardMarkup:
    toggle_label = "غیرفعال" if is_active else "فعال"
    toggle_action = "discount_disable_confirm" if is_active else "discount_enable"
    return inline_keyboard(
        [
            [("جزئیات", build_callback("m", "discount_detail", discount_id))],
            [(toggle_label, build_callback("m", toggle_action, discount_id))],
            [("بازگشت", build_callback("m", "discounts")), ("خانه", build_callback("m", "home"))],
        ]
    )


def master_seller_bot_actions(seller_bot_id: str) -> InlineKeyboardMarkup:
    return seller_bot_config_menu(seller_bot_id)


def broadcast_actions(broadcast_id: str, *, status: str = "draft") -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = [[("جزئیات", build_callback("m", "broadcast_detail", broadcast_id))]]
    if status == "draft":
        rows.append([("ارسال", build_callback("m", "broadcast_send_confirm", broadcast_id))])
    rows.append([("بازگشت", build_callback("m", "broadcast_history")), ("خانه", build_callback("m", "home"))])
    return inline_keyboard(rows)


def forced_join_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("افزودن چت", build_callback("m", "forced_join_add")),
                ("لیست چت ها", build_callback("m", "list_forced_join")),
            ],
            [("حذف چت", build_callback("m", "forced_join_remove"))],
            [("بازگشت", build_callback("m", "settings")), ("خانه", build_callback("m", "home"))],
        ]
    )


def forced_join_blocked_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [("✅ عضو شدم", build_callback("s", "home"))],
        ]
    )


def seller_buyer_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🛒 خرید سرویس", build_callback("s", "plans")),
                ("🛍 سرویس های من", build_callback("s", "services")),
            ],
            [
                ("👤 پروفایل", build_callback("s", "wallet")),
                ("💸 شارژ حساب", build_callback("s", "wallet")),
            ],
            [
                ("🎁 سرویس تستی (رایگان)", build_callback("s", "trial")),
            ],
            [
                ("🔗 راهنمای اتصال", build_callback("s", "guides")),
                ("📮 پشتیبانی آنلاین", build_callback("s", "support")),
            ],
            [("🔧 مدیریت", build_callback("s", "admin"))],
        ]
    )


def seller_admin_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("💳 پرداخت ها", build_callback("s", "admin_payments")),
                ("🧾 سفارش ها", build_callback("s", "admin_orders")),
            ],
            [
                ("💸 شارژ کیف پول", build_callback("s", "admin_wallet")),
                ("👤 مدیریت کاربران", build_callback("s", "admin_customers")),
            ],
            [
                ("📮 تیکت ها", build_callback("s", "admin_tickets")),
                ("🧑‍💻 پشتیبان", build_callback("s", "admin_support_settings")),
            ],
            [("🛒 تعرفه خدمات", build_callback("s", "admin_plans"))],
            [
                ("📊 گزارش فروش", build_callback("s", "admin_report")),
                ("📤 مدیریت پیام", build_callback("s", "admin_broadcast")),
            ],
            [("🪙 روش پرداخت", build_callback("s", "admin_payment_settings"))],
            [("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def admin_payment_settings_menu(*, has_crypto: bool) -> InlineKeyboardMarkup:
    label = "✏️ ویرایش پرداخت ارز دیجیتال" if has_crypto else "➕ ساخت پرداخت ارز دیجیتال"
    return inline_keyboard(
        [
            [(label, build_callback("s", "admin_crypto_payment_setup"))],
            [
                ("💳 پرداخت های در انتظار", build_callback("s", "admin_payments")),
                ("⬅️ بازگشت به مدیریت", build_callback("s", "admin")),
            ],
            [("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def admin_plans_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("➕ افزودن پلن", build_callback("s", "admin_plan_add")),
                ("🔄 بروزرسانی", build_callback("s", "admin_plans")),
            ],
            [("⬅️ بازگشت به مدیریت", build_callback("s", "admin")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def admin_plan_list_menu(plans: list[object]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for plan in plans[:30]:
        plan_id = str(getattr(plan, "id"))
        name = str(getattr(plan, "name", "پلن")).strip() or "پلن"
        owner = "اختصاصی" if getattr(plan, "reseller_id", None) else "عمومی"
        rows.append([(f"{name[:38]} | {owner}", build_callback("s", "admin_plan_detail", plan_id))])
    rows.append(
        [
            ("➕ افزودن پلن", build_callback("s", "admin_plan_add")),
            ("🔄 بروزرسانی", build_callback("s", "admin_plans")),
        ]
    )
    rows.append([("⬅️ بازگشت به مدیریت", build_callback("s", "admin")), ("📱 منوی اصلی", build_callback("s", "home"))])
    return inline_keyboard(rows)


def admin_plan_actions(plan_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("✏️ ویرایش پلن", build_callback("s", "admin_plan_edit", plan_id)),
                ("🗑 حذف پلن", build_callback("s", "admin_plan_delete_confirm", plan_id)),
            ],
            [("⬅️ بازگشت به پلن ها", build_callback("s", "admin_plans")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def admin_customers_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🔎 اطلاعات کاربر", build_callback("s", "admin_customer_search")),
                ("🔄 بروزرسانی", build_callback("s", "admin_customers")),
            ],
            [("⬅️ بازگشت به مدیریت", build_callback("s", "admin")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def admin_customer_card_actions(buyer_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🔎 اطلاعات کاربر", build_callback("s", "admin_customer_detail", buyer_id)),
                ("👁‍🗨 جستجو کاربر", build_callback("s", "admin_customer_search")),
            ],
            [("👤 مدیریت کاربران", build_callback("s", "admin_customers")), ("⬅️ بازگشت به مدیریت", build_callback("s", "admin"))],
        ]
    )


def admin_customer_detail_actions(buyer_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("📞 ارسال پیام به کاربر", build_callback("s", "admin_customer_message", buyer_id)),
                ("💸 تغییر موجودی", build_callback("s", "admin_customer_wallet", buyer_id)),
            ],
            [
                ("🚫 مسدود کردن", build_callback("s", "admin_customer_block", buyer_id)),
                ("👤 مدیریت کاربران", build_callback("s", "admin_customers")),
            ],
            [("⬅️ بازگشت به مدیریت", build_callback("s", "admin"))],
        ]
    )


def seller_report_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("📆 امروز", build_callback("s", "admin_report", "1")),
                ("📆 7 روز", build_callback("s", "admin_report", "7")),
                ("📆 30 روز", build_callback("s", "admin_report", "30")),
            ],
            [("🔎 بازه دلخواه", build_callback("s", "admin_report_custom"))],
            [("⬅️ بازگشت به مدیریت", build_callback("s", "admin")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def seller_section_menu(section: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            nav_row(scope="s", refresh_action=section, home_action="home")
        ]
    )


def plan_buy_button(plan_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🛒 خرید سرویس", build_callback("s", "buy", plan_id)),
                ("🔙 بازگشت", build_callback("s", "plans")),
                ("📱 منوی اصلی", build_callback("s", "home")),
            ]
        ]
    )


def plan_list_menu(plans: list[object]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for plan in plans:
        plan_id = str(getattr(plan, "id"))
        name = str(getattr(plan, "name", "پلن")).strip() or "پلن"
        rows.append([(name[:48], build_callback("s", "buy", plan_id))])
    rows.append(nav_row(scope="s", refresh_action="plans", home_action="home"))
    return inline_keyboard(rows)


def purchase_coupon_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🎁 کد تخفیف دارم", build_callback("s", "buy_coupon")),
                ("ادامه بدون کد", build_callback("s", "buy_no_coupon")),
            ],
            [("🛒 تعرفه خدمات", build_callback("s", "plans")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def purchase_confirm_menu() -> InlineKeyboardMarkup:
    return confirm_keyboard(
        scope="s",
        confirm_action="buy_create",
        cancel_action="buy_cancel",
    )


def payment_request_actions(order_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🔎 وضعیت سفارش", build_callback("s", "order_status", order_id)),
                ("📤 ارسال فیش", build_callback("s", "receipt_upload", order_id)),
            ],
            [("📮 پشتیبانی آنلاین", build_callback("s", "support")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def wallet_charge_request_actions(transaction_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("📤 ارسال فیش", build_callback("s", "wallet_receipt_upload", transaction_id)),
                ("💸 شارژ حساب", build_callback("s", "wallet")),
            ],
            [("📮 پشتیبانی آنلاین", build_callback("s", "support")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def service_actions(service_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [("ℹ️ اطلاعات سرویس", build_callback("s", "service_detail", service_id))],
            [
                ("🔗 دریافت لینک اشتراک", build_callback("s", "service_sub", service_id)),
                ("📷 کد QR", build_callback("s", "service_qr", service_id)),
            ],
            [
                ("🔄 تمدید سرویس", build_callback("s", "renew", service_id)),
            ],
            [("🔗 راهنمای اتصال", build_callback("s", "service_guide", service_id))],
            [("🔙 بازگشت به لیست سرویس ها", build_callback("s", "services")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def service_list_menu(services: list[object]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for service in services[:12]:
        service_id = str(getattr(service, "id"))
        username = str(getattr(service, "marzban_username", "سرویس")).strip() or "سرویس"
        status = "فعال" if getattr(service, "is_active", False) else "غیرفعال"
        rows.append([(f"{username[:32]} | {status}", build_callback("s", "service_detail", service_id))])
    rows.append(
        [
            ("🛒 خرید سرویس", build_callback("s", "plans")),
            ("💸 شارژ حساب", build_callback("s", "wallet")),
        ]
    )
    rows.append([("🔄 بروزرسانی", build_callback("s", "services")), ("📱 منوی اصلی", build_callback("s", "home"))])
    return inline_keyboard(rows)


def renewal_plan_button(plan_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("✅ انتخاب", build_callback("s", "renew_plan", plan_id)),
                ("🛍 سرویس های من", build_callback("s", "services")),
                ("📱 منوی اصلی", build_callback("s", "home")),
            ]
        ]
    )


def renewal_plan_list_menu(plans: list[object]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for plan in plans[:30]:
        plan_id = str(getattr(plan, "id"))
        name = str(getattr(plan, "name", "پلن")).strip() or "پلن"
        rows.append([(name[:48], build_callback("s", "renew_plan", plan_id))])
    rows.append([("🛍 سرویس های من", build_callback("s", "services")), ("📱 منوی اصلی", build_callback("s", "home"))])
    return inline_keyboard(rows)


def extra_volume_plan_button(plan_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("✅ انتخاب", build_callback("s", "extra_plan", plan_id)),
                ("🛍 سرویس های من", build_callback("s", "services")),
                ("📱 منوی اصلی", build_callback("s", "home")),
            ]
        ]
    )


def renewal_coupon_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🎁 کد تخفیف دارم", build_callback("s", "renew_coupon")),
                ("ادامه بدون کد", build_callback("s", "renew_no_coupon")),
            ],
            [("🛍 سرویس های من", build_callback("s", "services")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def renewal_confirm_menu() -> InlineKeyboardMarkup:
    return confirm_keyboard(
        scope="s",
        confirm_action="renew_create",
        cancel_action="renew_cancel",
    )


def extra_volume_coupon_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🎁 کد تخفیف دارم", build_callback("s", "extra_coupon")),
                ("ادامه بدون کد", build_callback("s", "extra_no_coupon")),
            ],
            [("🛍 سرویس های من", build_callback("s", "services")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def extra_volume_confirm_menu() -> InlineKeyboardMarkup:
    return confirm_keyboard(
        scope="s",
        confirm_action="extra_create",
        cancel_action="extra_cancel",
    )


def wallet_charge_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("100,000", build_callback("s", "wallet_add", "100000")),
                ("250,000", build_callback("s", "wallet_add", "250000")),
            ],
            [
                ("500,000", build_callback("s", "wallet_add", "500000")),
                ("💰 مبلغ دلخواه", build_callback("s", "wallet_custom")),
            ],
            [("❌ انصراف", build_callback("s", "wallet")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def wallet_transaction_actions(transaction_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🔎 جزئیات", build_callback("s", "wallet_tx", transaction_id)),
                ("💸 شارژ حساب", build_callback("s", "wallet")),
            ],
            [("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


def support_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("📮 تیکت های من", build_callback("s", "tickets")),
                ("🎟 ثبت تیکت", build_callback("s", "ticket_open")),
            ],
            [
                ("🔗 راهنمای اتصال", build_callback("s", "guides")),
                ("❌ انصراف", build_callback("s", "ticket_cancel")),
                ("📱 منوی اصلی", build_callback("s", "home")),
            ],
        ]
    )


def buyer_ticket_actions(ticket_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("جزئیات", build_callback("s", "ticket_detail", ticket_id)),
                ("پاسخ", build_callback("s", "ticket_reply", ticket_id)),
            ],
            [("بازگشت", build_callback("s", "tickets")), ("خانه", build_callback("s", "home"))],
        ]
    )


def admin_payment_actions(payment_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("جزئیات", build_callback("s", "pay_detail", payment_id)),
                ("تایید", build_callback("s", "pay_ok", payment_id)),
            ],
            [
                ("رد", build_callback("s", "pay_reject_confirm", payment_id)),
                ("پرداخت ها", build_callback("s", "admin_payments")),
            ],
            [("بازگشت", build_callback("s", "admin_payments")), ("خانه مدیریت", build_callback("s", "admin"))],
        ]
    )


def admin_order_actions(order_id: str, *, renewal: bool = False, extra_volume: bool = False) -> InlineKeyboardMarkup:
    if extra_volume:
        action = "confirm_extra_volume"
        label = "اعمال حجم اضافه"
    elif renewal:
        action = "confirm_renewal"
        label = "اعمال تمدید"
    else:
        action = "confirm_provision"
        label = "ساخت سرویس"
    return inline_keyboard(
        [
            [
                (label, build_callback("s", action, order_id)),
                ("پرداخت ها", build_callback("s", "admin_payments")),
            ],
            [("بازگشت", build_callback("s", "admin_payments")), ("خانه مدیریت", build_callback("s", "admin"))],
        ]
    )


def admin_wallet_charge_actions(transaction_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("تایید", build_callback("s", "wallet_ok", transaction_id)),
                ("شارژهای کیف پول", build_callback("s", "admin_wallet")),
            ],
            [("بازگشت", build_callback("s", "admin_wallet")), ("خانه مدیریت", build_callback("s", "admin"))],
        ]
    )


def admin_ticket_actions(ticket_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("جزئیات", build_callback("s", "admin_ticket_detail", ticket_id)),
                ("پاسخ", build_callback("s", "admin_ticket_reply", ticket_id)),
            ],
            [
                ("بستن", build_callback("s", "ticket_close", ticket_id)),
                ("تیکت ها", build_callback("s", "admin_tickets")),
            ],
            [("بازگشت", build_callback("s", "admin_tickets")), ("خانه مدیریت", build_callback("s", "admin"))],
        ]
    )


def admin_support_settings_menu(*, has_support: bool) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = [
        [("✏️ تنظیم پشتیبان", build_callback("s", "admin_support_set"))],
    ]
    if has_support:
        rows.append([("🗑 حذف پشتیبان", build_callback("s", "admin_support_delete_confirm"))])
    rows.append([("📮 تیکت ها", build_callback("s", "admin_tickets")), ("⬅️ بازگشت به مدیریت", build_callback("s", "admin"))])
    return inline_keyboard(rows)
