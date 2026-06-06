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
    return inline_keyboard(
        [
            [
                ("Refresh", build_callback("m", section)),
                ("Home", build_callback("m", "home")),
            ]
        ]
    )


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
                ("QR Code", build_callback("s", "service_qr", service_id)),
                ("Renew", build_callback("s", "renew", service_id)),
            ],
            [("Home", build_callback("s", "home"))],
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
