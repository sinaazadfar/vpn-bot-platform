from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from vpn_bot_platform.common.ui.callbacks import build_callback


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=callback_data) for text, callback_data in row]
            for row in rows
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
        [
            ("Refresh", build_callback("m", section)),
            ("Home", build_callback("m", "home")),
        ]
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
            [("Resellers", build_callback("m", "resellers"))],
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
            [("Seller Bots", build_callback("m", "seller_bots"))],
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
            [
                ("Refresh", build_callback("s", section)),
                ("Home", build_callback("s", "home")),
            ]
        ]
    )


def plan_buy_button(plan_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Buy", build_callback("s", "buy", plan_id)),
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
            [("Home", build_callback("s", "home"))],
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
            [("Home", build_callback("s", "home"))],
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
            [("Admin Home", build_callback("s", "admin"))],
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
            [("Admin Home", build_callback("s", "admin"))],
        ]
    )


def admin_wallet_charge_actions(transaction_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Approve", build_callback("s", "wallet_ok", transaction_id)),
                ("Wallet Charges", build_callback("s", "admin_wallet")),
            ],
            [("Admin Home", build_callback("s", "admin"))],
        ]
    )


def admin_ticket_actions(ticket_id: str) -> InlineKeyboardMarkup:
    return inline_keyboard(
        [
            [
                ("Close", build_callback("s", "ticket_close", ticket_id)),
                ("Tickets", build_callback("s", "admin_tickets")),
            ],
            [("Admin Home", build_callback("s", "admin"))],
        ]
    )
