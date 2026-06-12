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
    return inline_keyboard([[("❌ Cancel", build_callback(scope, cancel_action))]])


def reply_keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
    )


def master_reply_menu() -> ReplyKeyboardMarkup:
    return reply_keyboard(
        [
            ["Seller Bots", "Add Seller Bot"],
        ]
    )


def seller_buyer_reply_menu() -> ReplyKeyboardMarkup:
    return reply_keyboard(
        [
            ["🛒 خرید سرویس", "🛍 سرویس های من"],
            ["💸 شارژ حساب", "👤 پروفایل"],
            ["🎁 سرویس تستی (رایگان)"],
            ["🔗 راهنمای اتصال", "📮 پشتیبانی آنلاین"],
        ]
    )


def seller_admin_reply_menu() -> ReplyKeyboardMarkup:
    return reply_keyboard(
        [
            ["💳 پرداخت ها", "🧾 سفارش ها"],
            ["💸 شارژ کیف پول", "👤 مدیریت کاربران"],
            ["📮 تیکت ها", "🛒 تعرفه خدمات"],
            ["📊 گزارش فروش", "📱 منوی اصلی"],
        ]
    )


def master_main_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [("🤖 Seller Bots", build_callback("m", "seller_bots"))],
            [("➕ Add Seller Bot", build_callback("m", "add_seller_bot"))],
            [
                ("⚙️ Platform Settings", build_callback("m", "platform_settings")),
                ("📊 Reports", build_callback("m", "reports")),
            ],
        ]
    )


def master_section_menu(section: str) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    if section == "resellers":
        rows.append(
            [
                ("Add Reseller", build_callback("m", "guide_add_reseller")),
                ("Rename", build_callback("m", "guide_rename_reseller")),
            ]
        )
    elif section == "seller_bots":
        rows.append(
            [
                ("➕ Add Seller Bot", build_callback("m", "add_seller_bot")),
                ("🔎 Search", build_callback("m", "seller_search")),
            ]
        )
        rows.append([("🧩 Bot Templates", build_callback("m", "external_bots"))])
    elif section == "platform_settings":
        rows.append(
            [
                ("Resellers", build_callback("m", "resellers")),
                ("Panels", build_callback("m", "panels")),
            ]
        )
        rows.append(
            [
                ("Plans", build_callback("m", "plans")),
                ("Discounts", build_callback("m", "discounts")),
            ]
        )
        rows.append(
            [
                ("Broadcasts", build_callback("m", "broadcasts")),
                ("System", build_callback("m", "system")),
            ]
        )
    elif section == "external_bots":
        rows.append(
            [
                ("Add Template", build_callback("m", "guide_add_external_template")),
                ("Add External Bot", build_callback("m", "guide_add_external_seller_bot")),
            ]
        )
    elif section == "panels":
        rows.append(
            [
                ("Add Token Panel", build_callback("m", "guide_add_panel_token")),
                ("Add Login Panel", build_callback("m", "guide_add_panel_password")),
            ]
        )
        rows.append([("Assign Panel", build_callback("m", "guide_assign_panel"))])
    elif section == "plans":
        rows.append(
            [
                ("Add Global Plan", build_callback("m", "guide_add_global_plan")),
                ("Add Seller Plan", build_callback("m", "guide_add_reseller_plan")),
            ]
        )
    elif section == "discounts":
        rows.append([("Add Discount", build_callback("m", "guide_add_discount"))])
    elif section == "broadcasts":
        rows.append(
            [
                ("Create Broadcast", build_callback("m", "guide_global_broadcast")),
                ("Drafts", build_callback("m", "broadcast_history")),
            ]
        )
    elif section == "settings":
        rows.append(
            [
                ("Forced Join", build_callback("m", "settings_forced_join")),
                ("Rate Limits", build_callback("m", "settings_rate_limits")),
            ]
        )
        rows.append(
            [
                ("Trial", build_callback("m", "settings_trial")),
                ("Payments", build_callback("m", "settings_payments")),
            ]
        )
    elif section == "reports":
        rows.append(
            [
                ("Today", build_callback("m", "report_1")),
                ("7 Days", build_callback("m", "report_7")),
                ("30 Days", build_callback("m", "report_30")),
            ]
        )
        rows.append([("Custom Days", build_callback("m", "report_custom"))])
    elif section == "system":
        rows.append(
            [
                ("Health", build_callback("m", "system_health")),
                ("Version", build_callback("m", "system_version")),
            ]
        )
        rows.append(
            [
                ("Backup", build_callback("m", "system_backup")),
                ("Audit Logs", build_callback("m", "system_audit")),
            ]
        )
        rows.append([("Recent Errors", build_callback("m", "system_errors"))])
    rows.append(
        nav_row(scope="m", refresh_action=section, home_action="home")
    )
    return inline_keyboard(rows)


def reseller_actions(telegram_id: int) -> InlineKeyboardMarkup:
    value = str(telegram_id)
    return inline_keyboard(
        [
            [
                ("Activate", build_callback("m", "reseller_active", value)),
                ("Suspend", build_callback("m", "reseller_suspended", value)),
            ],
            [
                ("Disable", build_callback("m", "reseller_disabled", value)),
                ("Cancel", build_callback("m", "resellers")),
                ("Home", build_callback("m", "home")),
            ],
        ]
    )


def external_template_actions(template_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Sync", build_callback("m", "ext_sync", template_id)),
                ("External Bots", build_callback("m", "external_bots")),
            ],
            nav_row(scope="m", back_action="seller_bots", home_action="home"),
        ]
    )


def seller_bot_list_menu(
    *,
    page: int,
    total_pages: int,
    seller_bots: list[object] | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = [
        [
            ("➕ Add Seller Bot", build_callback("m", "add_seller_bot")),
            ("🔎 Search", build_callback("m", "seller_search")),
        ]
    ]
    for seller_bot in seller_bots or []:
        bot_id = str(getattr(seller_bot, "id"))
        name = str(getattr(seller_bot, "name", "Seller Bot")).strip() or "Seller Bot"
        status = str(getattr(seller_bot, "status", "")).strip()
        label = f"{name[:24]} | {status[:12]}" if status else name[:32]
        rows.append([(label, build_callback("m", "seller_select", bot_id))])
    page_row = pagination_row(scope="m", action="seller_bots", page=page, total_pages=total_pages)
    if page_row:
        rows.append(page_row)
    rows.append(nav_row(scope="m", refresh_action="seller_bots", home_action="home"))
    return inline_keyboard(rows)


def seller_bot_config_menu(seller_bot_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("🧩 Configure", build_callback("m", "seller_detail", seller_bot_id)),
                ("📡 Bot Panel", build_callback("m", "seller_config_panel", seller_bot_id)),
            ],
            [
                ("💰 Pricing Rules", build_callback("m", "seller_config_pricing", seller_bot_id)),
                ("👥 Bot Admins", build_callback("m", "seller_config_admins", seller_bot_id)),
            ],
            [
                ("Start", build_callback("m", "seller_start", seller_bot_id)),
                ("Stop", build_callback("m", "seller_stop", seller_bot_id)),
            ],
            [
                ("Health", build_callback("m", "seller_health", seller_bot_id)),
                ("Logs", build_callback("m", "seller_logs", seller_bot_id)),
            ],
            [("Disable", build_callback("m", "seller_disable", seller_bot_id))],
            [("Back", build_callback("m", "seller_bots")), ("Home", build_callback("m", "home"))],
        ]
    )


def seller_bot_type_menu(*, has_external_templates: bool) -> InlineKeyboardMarkup:
    rows = [[("Our Seller Bot", build_callback("m", "sellerbot_type", "native"))]]
    if has_external_templates:
        rows.append([("External Template Bot", build_callback("m", "sellerbot_type", "external"))])
    rows.append([("Cancel", build_callback("m", "sellerbot_cancel")), ("Home", build_callback("m", "home"))])
    return inline_keyboard(rows)


def reseller_card_actions(telegram_id: int) -> InlineKeyboardMarkup:
    value = str(telegram_id)
    return inline_keyboard(
        [
            [("Details", build_callback("m", "reseller_detail", value))],
            [
                ("Rename", build_callback("m", "reseller_rename_select", value)),
            ],
            [
                ("Activate", build_callback("m", "reseller_active", value)),
                ("Suspend", build_callback("m", "reseller_suspended", value)),
                ("Disable", build_callback("m", "reseller_disabled", value)),
            ],
            [("Back", build_callback("m", "resellers")), ("Home", build_callback("m", "home"))],
        ]
    )


def reseller_detail_actions(telegram_id: int) -> InlineKeyboardMarkup:
    value = str(telegram_id)
    return inline_keyboard(
        [
            [
                ("Seller Bots", build_callback("m", "reseller_seller_bots", value)),
                ("Plans", build_callback("m", "reseller_plans", value)),
            ],
            [("Panel Assignments", build_callback("m", "reseller_panels", value))],
            [
                ("Rename", build_callback("m", "reseller_rename_select", value)),
                ("Status", build_callback("m", "reseller_status_menu", value)),
            ],
            [("Back", build_callback("m", "resellers")), ("Home", build_callback("m", "home"))],
        ]
    )


def reseller_list_menu(*, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = [
        [
            ("Add Reseller", build_callback("m", "guide_add_reseller")),
            ("Rename", build_callback("m", "guide_rename_reseller")),
        ]
    ]
    page_row = pagination_row(scope="m", action="resellers", page=page, total_pages=total_pages)
    if page_row:
        rows.append(page_row)
    rows.append(nav_row(scope="m", refresh_action="resellers", home_action="home"))
    return inline_keyboard(rows)


def panel_actions(panel_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [("Details", build_callback("m", "panel_detail", panel_id))],
            [
                ("Test Connection", build_callback("m", "panel_test", panel_id)),
                ("Disable", build_callback("m", "panel_disable_confirm", panel_id)),
            ],
            [("Assign To Reseller", build_callback("m", "guide_assign_panel"))],
            [("Back", build_callback("m", "panels")), ("Home", build_callback("m", "home"))],
        ]
    )


def plan_actions(plan_id: str, *, is_active: bool = True) -> InlineKeyboardMarkup:
    toggle_label = "Disable" if is_active else "Enable"
    toggle_action = "plan_disable_confirm" if is_active else "plan_enable"
    return inline_keyboard(
        [
            [("Details", build_callback("m", "plan_detail", plan_id))],
            [(toggle_label, build_callback("m", toggle_action, plan_id))],
            [("Back", build_callback("m", "plans")), ("Home", build_callback("m", "home"))],
        ]
    )


def discount_actions(discount_id: str, *, is_active: bool = True) -> InlineKeyboardMarkup:
    toggle_label = "Disable" if is_active else "Enable"
    toggle_action = "discount_disable_confirm" if is_active else "discount_enable"
    return inline_keyboard(
        [
            [("Details", build_callback("m", "discount_detail", discount_id))],
            [(toggle_label, build_callback("m", toggle_action, discount_id))],
            [("Back", build_callback("m", "discounts")), ("Home", build_callback("m", "home"))],
        ]
    )


def master_seller_bot_actions(seller_bot_id: str) -> InlineKeyboardMarkup:
    return seller_bot_config_menu(seller_bot_id)


def broadcast_actions(broadcast_id: str, *, status: str = "draft") -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = [[("Details", build_callback("m", "broadcast_detail", broadcast_id))]]
    if status == "draft":
        rows.append([("Send", build_callback("m", "broadcast_send_confirm", broadcast_id))])
    rows.append([("Back", build_callback("m", "broadcast_history")), ("Home", build_callback("m", "home"))])
    return inline_keyboard(rows)


def forced_join_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Add Chat", build_callback("m", "forced_join_add")),
                ("List Chats", build_callback("m", "list_forced_join")),
            ],
            [("Remove Chat", build_callback("m", "forced_join_remove"))],
            [("Back", build_callback("m", "settings")), ("Home", build_callback("m", "home"))],
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
                ("🛒 تعرفه خدمات", build_callback("s", "admin_plans")),
            ],
            [
                ("📊 گزارش فروش", build_callback("s", "admin_report")),
                ("📤 مدیریت پیام", build_callback("s", "admin_broadcast")),
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


def admin_plan_actions(plan_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [("🗑 حذف پلن", build_callback("s", "admin_plan_delete_confirm", plan_id))],
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
        name = str(getattr(plan, "name", "Plan")).strip() or "Plan"
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


def service_actions(service_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [("ℹ️ اطلاعات سرویس", build_callback("s", "service_detail", service_id))],
            [
                ("🔗 دریافت لینک اشتراک", build_callback("s", "service_sub", service_id)),
                ("📷 QR Code", build_callback("s", "service_qr", service_id)),
            ],
            [
                ("افزایش اعتبار زمانی", build_callback("s", "renew", service_id)),
                ("خرید حجم اضافه", build_callback("s", "extra_volume", service_id)),
            ],
            [("🔗 راهنمای اتصال", build_callback("s", "service_guide", service_id))],
            [("🔙 بازگشت به لیست سرویس ها", build_callback("s", "services")), ("📱 منوی اصلی", build_callback("s", "home"))],
        ]
    )


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
                ("🎟 ارسال پیام به پشتیبانی", build_callback("s", "ticket_open")),
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
                ("Details", build_callback("s", "ticket_detail", ticket_id)),
                ("Reply", build_callback("s", "ticket_reply", ticket_id)),
            ],
            [("Back", build_callback("s", "tickets")), ("Home", build_callback("s", "home"))],
        ]
    )


def admin_payment_actions(payment_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Details", build_callback("s", "pay_detail", payment_id)),
                ("Approve", build_callback("s", "pay_ok", payment_id)),
            ],
            [
                ("Reject", build_callback("s", "pay_reject_confirm", payment_id)),
                ("Payments", build_callback("s", "admin_payments")),
            ],
            [("Back", build_callback("s", "admin_payments")), ("Admin Home", build_callback("s", "admin"))],
        ]
    )


def admin_order_actions(order_id: str, *, renewal: bool = False, extra_volume: bool = False) -> InlineKeyboardMarkup:
    if extra_volume:
        action = "confirm_extra_volume"
        label = "Apply Extra Volume"
    elif renewal:
        action = "confirm_renewal"
        label = "Apply Renewal"
    else:
        action = "confirm_provision"
        label = "Provision"
    return inline_keyboard(
        [
            [
                (label, build_callback("s", action, order_id)),
                ("Payments", build_callback("s", "admin_payments")),
            ],
            [("Back", build_callback("s", "admin_payments")), ("Admin Home", build_callback("s", "admin"))],
        ]
    )


def admin_wallet_charge_actions(transaction_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Approve", build_callback("s", "wallet_ok", transaction_id)),
                ("Wallet Charges", build_callback("s", "admin_wallet")),
            ],
            [("Back", build_callback("s", "admin_wallet")), ("Admin Home", build_callback("s", "admin"))],
        ]
    )


def admin_ticket_actions(ticket_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Details", build_callback("s", "admin_ticket_detail", ticket_id)),
                ("Reply", build_callback("s", "admin_ticket_reply", ticket_id)),
            ],
            [
                ("Close", build_callback("s", "ticket_close", ticket_id)),
                ("Tickets", build_callback("s", "admin_tickets")),
            ],
            [("Back", build_callback("s", "admin_tickets")), ("Admin Home", build_callback("s", "admin"))],
        ]
    )
