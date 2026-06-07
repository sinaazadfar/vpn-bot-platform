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
        ("Prev", build_callback(scope, action, str(previous_page))),
        (f"{page}/{total_pages}", build_callback(scope, action, str(page))),
        ("Next", build_callback(scope, action, str(next_page))),
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
        row.append(("Back", build_callback(scope, back_action)))
    if refresh_action:
        row.append(("Refresh", build_callback(scope, refresh_action)))
    if cancel_action:
        row.append(("Cancel", build_callback(scope, cancel_action)))
    row.append(("Home", build_callback(scope, home_action)))
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
                ("Confirm", build_callback(scope, confirm_action, value)),
                ("Cancel", build_callback(scope, cancel_action, value)),
            ]
        ]
    )


def reply_keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
    )


def master_reply_menu() -> ReplyKeyboardMarkup:
    return reply_keyboard(
        [
            ["Resellers", "Seller Bots"],
            ["Panels", "Plans"],
            ["Reports", "Settings"],
        ]
    )


def seller_buyer_reply_menu() -> ReplyKeyboardMarkup:
    return reply_keyboard(
        [
            ["Buy VPN", "My Services"],
            ["Wallet", "Support"],
            ["Trial", "Guides"],
        ]
    )


def seller_admin_reply_menu() -> ReplyKeyboardMarkup:
    return reply_keyboard(
        [
            ["Pending Payments", "Wallet Charges"],
            ["Tickets", "Sales Report"],
            ["Buyer Home"],
        ]
    )


def master_main_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Resellers", build_callback("m", "resellers")),
                ("Seller Bots", build_callback("m", "seller_bots")),
            ],
            [
                ("Panels", build_callback("m", "panels")),
                ("Plans", build_callback("m", "plans")),
            ],
            [
                ("Discounts", build_callback("m", "discounts")),
                ("Broadcasts", build_callback("m", "broadcasts")),
            ],
            [
                ("Reports", build_callback("m", "reports")),
                ("Settings", build_callback("m", "settings")),
            ],
            [("System", build_callback("m", "system"))],
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
                ("Add Seller Bot", build_callback("m", "guide_add_seller_bot")),
                ("BotFather", build_callback("m", "guide_botfather")),
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
                ("Send Broadcast", build_callback("m", "guide_send_global_broadcast")),
            ]
        )
    elif section == "settings":
        rows.append(
            [
                ("Forced Join", build_callback("m", "guide_set_forced_join")),
                ("List Forced Join", build_callback("m", "list_forced_join")),
            ]
        )
    elif section == "system":
        rows.append(
            [
                ("Today", build_callback("m", "report_1")),
                ("7 Days", build_callback("m", "report_7")),
            ]
        )
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


def reseller_card_actions(telegram_id: int) -> InlineKeyboardMarkup:
    value = str(telegram_id)
    return inline_keyboard(
        [
            [
                ("Activate", build_callback("m", "reseller_active", value)),
                ("Suspend", build_callback("m", "reseller_suspended", value)),
                ("Disable", build_callback("m", "reseller_disabled", value)),
            ],
            [("Back", build_callback("m", "resellers")), ("Home", build_callback("m", "home"))],
        ]
    )


def master_seller_bot_actions(seller_bot_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
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


def seller_buyer_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Buy VPN", build_callback("s", "plans")),
                ("My Services", build_callback("s", "services")),
            ],
            [
                ("Wallet", build_callback("s", "wallet")),
                ("Trial", build_callback("s", "trial")),
            ],
            [
                ("Support", build_callback("s", "support")),
                ("Guides", build_callback("s", "guides")),
            ],
            [("Admin", build_callback("s", "admin"))],
        ]
    )


def seller_admin_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Pending Payments", build_callback("s", "admin_payments")),
                ("Wallet Charges", build_callback("s", "admin_wallet")),
            ],
            [
                ("Tickets", build_callback("s", "admin_tickets")),
                ("Sales Report", build_callback("s", "admin_report")),
            ],
            [
                ("Broadcast", build_callback("s", "admin_broadcast")),
                ("Buyer Home", build_callback("s", "home")),
            ],
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
                ("Buy", build_callback("s", "buy", plan_id)),
                ("Back", build_callback("s", "plans")),
                ("Home", build_callback("s", "home")),
            ]
        ]
    )


def service_actions(service_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Subscription", build_callback("s", "service_sub", service_id)),
                ("QR Code", build_callback("s", "service_qr", service_id)),
            ],
            [
                ("Renew", build_callback("s", "renew", service_id)),
                ("Services", build_callback("s", "services")),
            ],
            [("Back", build_callback("s", "services")), ("Home", build_callback("s", "home"))],
        ]
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
                ("Custom", build_callback("s", "wallet_custom")),
            ],
            [("Cancel", build_callback("s", "wallet")), ("Home", build_callback("s", "home"))],
        ]
    )


def support_menu() -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("My Tickets", build_callback("s", "tickets")),
                ("Open Ticket", build_callback("s", "ticket_open")),
            ],
            [
                ("Guides", build_callback("s", "guides")),
                ("Cancel", build_callback("s", "ticket_cancel")),
                ("Home", build_callback("s", "home")),
            ],
        ]
    )


def admin_payment_actions(payment_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Approve", build_callback("s", "pay_ok", payment_id)),
                ("Payments", build_callback("s", "admin_payments")),
            ],
            [("Back", build_callback("s", "admin_payments")), ("Admin Home", build_callback("s", "admin"))],
        ]
    )


def admin_order_actions(order_id: str, *, renewal: bool = False) -> InlineKeyboardMarkup:
    action = "apply_renewal" if renewal else "provision_order"
    label = "Apply Renewal" if renewal else "Provision"
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
                ("Close", build_callback("s", "ticket_close", ticket_id)),
                ("Tickets", build_callback("s", "admin_tickets")),
            ],
            [("Back", build_callback("s", "admin_tickets")), ("Admin Home", build_callback("s", "admin"))],
        ]
    )
