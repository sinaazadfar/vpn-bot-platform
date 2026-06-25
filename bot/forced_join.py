from __future__ import annotations

import logging
import re

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    Chat,
    ChatMemberAdministrator,
    ChatMemberMember,
    ChatMemberOwner,
    ChatMemberRestricted,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from bot.db import RequiredChat

logger = logging.getLogger(__name__)


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


def is_active_chat_member(member: object) -> bool:
    if isinstance(member, (ChatMemberOwner, ChatMemberAdministrator, ChatMemberMember)):
        return True
    if isinstance(member, ChatMemberRestricted):
        return bool(member.is_member)
    return False


def required_chat_targets(chat: RequiredChat) -> list[int | str]:
    targets: list[int | str] = [chat.chat_id]
    if not chat.invite_link:
        return targets
    match = re.search(r"t\.me/(@?[\w_]+)", chat.invite_link, re.IGNORECASE)
    if not match:
        return targets
    slug = match.group(1).lstrip("@")
    if slug and not slug.startswith("+"):
        handle = f"@{slug}"
        if handle not in targets:
            targets.append(handle)
    return targets


async def is_user_member_of_chat(bot: Bot, chat: RequiredChat, user_id: int) -> tuple[bool, TelegramAPIError | None]:
    last_error: TelegramAPIError | None = None
    for target in required_chat_targets(chat):
        try:
            member = await bot.get_chat_member(target, user_id)
        except TelegramAPIError as exc:
            last_error = exc
            logger.warning(
                "forced_join get_chat_member failed chat_id=%s target=%r user_id=%s: %s",
                chat.chat_id,
                target,
                user_id,
                exc,
            )
            continue
        return is_active_chat_member(member), None
    return False, last_error


async def check_forced_join(bot: Bot, user_id: int, chats: list[RequiredChat]) -> bool:
    allowed, _ = await evaluate_forced_join(bot, user_id, chats)
    return allowed


async def evaluate_forced_join(
    bot: Bot,
    user_id: int,
    chats: list[RequiredChat],
) -> tuple[bool, str | None]:
    verify_error = False
    for chat in chats:
        joined, error = await is_user_member_of_chat(bot, chat, user_id)
        if joined:
            continue
        if error is not None:
            verify_error = True
            continue
        return False, "not_member"
    if verify_error:
        return False, "verify_error"
    return True, None


def forced_join_text(chats: list[RequiredChat]) -> str:
    if len(chats) == 1:
        label = chats[0].title or "کانال ما"
        return (
            "سلام! 👋\n\n"
            f"برای استفاده از ربات، لطفاً اول در کانال «{label}» عضو شو "
            "تا از آخرین اخبار، آموزش‌ها و تخفیف‌ها با خبر بشی.\n\n"
            "روی دکمه زیر بزن، عضو شو و بعد «عضو شدم» رو انتخاب کن."
        )

    lines = [
        "سلام! 👋",
        "",
        "برای ادامه، لطفاً در کانال‌های زیر عضو شو:",
        "",
    ]
    for chat in chats:
        label = chat.title or "کانال"
        lines.append(f"📢 {label}")
    lines.extend(
        [
            "",
            "از دکمه‌های زیر وارد هر کانال شو و بعد از عضویت، «عضو شدم» رو بزن.",
        ]
    )
    return "\n".join(lines)


def forced_join_recheck_failed_alert(reason: str | None = None) -> str:
    if reason == "verify_error":
        return (
            "الان نمی‌تونیم عضویتت رو بررسی کنیم.\n"
            "لطفاً به ادمین بگو ربات را ادمین کانال کند و دوباره امتحان کن."
        )
    return "هنوز در همه کانال‌ها عضو نشدی 🙏\nلطفاً اول عضو شو و دوباره «عضو شدم» رو بزن."


def forced_join_success_text() -> str:
    return "عالی! عضویتت تأیید شد ✅\n\nخوش اومدی — از منوی زیر می‌تونی شروع کنی."


def forced_join_keyboard(chats: list[RequiredChat]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for chat in chats:
        label = chat.title or "کانال"
        url = chat.invite_link or f"https://t.me/c/{str(chat.chat_id).removeprefix('-100')}"
        rows.append([InlineKeyboardButton(text=f"📢 عضویت در {label}", url=url)])
    rows.append([InlineKeyboardButton(text="✅ عضو شدم، ادامه بده", callback_data="join:recheck")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
