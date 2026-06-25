from __future__ import annotations

import re

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Chat, InlineKeyboardButton, InlineKeyboardMarkup

from bot.db import RequiredChat


def chat_ref_to_get_chat_target(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty_ref")
    if text.lstrip("-").isdigit():
        return text
    if text.startswith("@"):
        return text
    match = re.search(r"(?:https?://)?(?:www\.)?t\.me/([^\s/?#]+)", text, re.IGNORECASE)
    if match:
        slug = match.group(1)
        if slug.startswith("+"):
            return text if text.startswith("http") else f"https://t.me/{slug}"
        return f"@{slug}"
    if re.fullmatch(r"[\w_]+", text):
        return f"@{text}"
    raise ValueError("invalid_ref")


def invite_link_for_chat(chat: Chat, original_raw: str) -> str:
    text = (original_raw or "").strip()
    if text.startswith("http") and "t.me/" in text:
        return text
    if chat.username:
        return f"https://t.me/{chat.username}"
    return ""


async def resolve_required_chat(bot: Bot, raw: str) -> tuple[int, str, str]:
    target = chat_ref_to_get_chat_target(raw)
    try:
        chat = await bot.get_chat(target)
    except TelegramAPIError as exc:
        raise ValueError("کانال پیدا نشد. ربات را ادمین کانال کنید.") from exc
    title = chat.title or (f"@{chat.username}" if chat.username else str(chat.id))
    return chat.id, title, invite_link_for_chat(chat, raw)


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
        rows.append([InlineKeyboardButton(text=f"📢 {label}", url=url)])
    rows.append([InlineKeyboardButton(text="بررسی مجدد", callback_data="join:recheck")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
