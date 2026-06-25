from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db import RequiredChat


async def check_forced_join(bot: Bot, user_id: int, chats: list[RequiredChat]) -> bool:
    for chat in chats:
        try:
            member = await bot.get_chat_member(chat.chat_id, user_id)
        except TelegramAPIError:
            return False
        if member.status in {"left", "kicked"}:
            return False
    return True


def forced_join_text(chats: list[RequiredChat]) -> str:
    lines = ["عضویت اجباری", "", "برای استفاده از ربات ابتدا در کانال‌های زیر عضو شوید:", ""]
    for chat in chats:
        label = chat.title or str(chat.chat_id)
        lines.append(f"• {label}")
    lines.extend(["", "بعد از عضویت روی «بررسی مجدد» بزنید."])
    return "\n".join(lines)


def forced_join_keyboard(chats: list[RequiredChat]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for chat in chats:
        label = chat.title or "کانال"
        url = chat.invite_link or f"https://t.me/c/{str(chat.chat_id).removeprefix('-100')}"
        if chat.invite_link:
            rows.append([InlineKeyboardButton(text=f"📢 {label}", url=chat.invite_link)])
    rows.append([InlineKeyboardButton(text="بررسی مجدد", callback_data="join:recheck")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
