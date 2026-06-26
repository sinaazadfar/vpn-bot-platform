from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import constants as c


@dataclass(frozen=True)
class AppGuide:
    key: str
    name: str
    download_url: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class PlatformGuide:
    key: str
    name: str
    emoji: str
    apps: tuple[AppGuide, ...]


PLATFORMS: tuple[PlatformGuide, ...] = (
    PlatformGuide(
        key="and",
        name="اندروید",
        emoji="🤖",
        apps=(
            AppGuide(
                key="happ",
                name="Happ",
                download_url="https://play.google.com/store/apps/details?id=com.happproxy",
                steps=(
                    "Happ را از Google Play یا لینک دانلود نصب کنید.",
                    "در ربات به «اشتراک‌های من» بروید و «لینک اشتراک» را کپی کنید.",
                    "Happ را باز کنید و دکمه + را بزنید.",
                    "گزینه «افزودن اشتراک» یا Import from Clipboard را انتخاب کنید.",
                    "لینک اشتراک را Paste کنید یا از کلیپ‌بورد وارد کنید.",
                    "پس از لود سرورها، یکی را انتخاب کنید.",
                    "دکمه اتصال را بزنید و مجوز VPN را تأیید کنید.",
                ),
            ),
            AppGuide(
                key="v2rayng",
                name="v2rayNG",
                download_url="https://github.com/2dust/v2rayNG/releases",
                steps=(
                    "اپ v2rayNG را از لینک دانلود نصب کنید.",
                    "در ربات به «اشتراک‌های من» بروید و «لینک اشتراک» را کپی کنید.",
                    "v2rayNG را باز کنید و از منوی سه‌نقطه گزینه «Subscription group setting» را بزنید.",
                    "روی + بزنید، لینک اشتراک را در فیلد URL بچسبانید و «OK» را بزنید.",
                    "از منوی سه‌نقطه «Update subscription» را بزنید تا کانفیگ‌ها لود شوند.",
                    "یک کانفیگ را انتخاب کنید و دکمه اتصال (V) پایین صفحه را بزنید.",
                    "در اولین اتصال اجازه VPN را تأیید کنید.",
                ),
            ),
            AppGuide(
                key="hiddify",
                name="Hiddify",
                download_url="https://play.google.com/store/apps/details?id=app.hiddify.com",
                steps=(
                    "Hiddify را از گوگل‌پلی یا لینک دانلود نصب کنید.",
                    "در ربات «لینک اشتراک» را از بخش اشتراک‌های من کپی کنید.",
                    "Hiddify را باز کنید و «Add from clipboard» یا «افزودن اشتراک» را بزنید.",
                    "اگر لینک در کلیپ‌بورد باشد، خودکار شناسایی می‌شود؛ در غیر این صورت دستی Paste کنید.",
                    "پروفایل جدید را انتخاب کنید.",
                    "دکمه اتصال (Connect) را بزنید و مجوز VPN را تأیید کنید.",
                ),
            ),
            AppGuide(
                key="nekobox",
                name="NekoBox",
                download_url="https://github.com/MatsuriDayo/NekoBoxForAndroid/releases",
                steps=(
                    "NekoBox را از لینک دانلود (فایل APK) نصب کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "در NekoBox به Groups بروید و «New Group» یا + را بزنید.",
                    "نوع Subscription را انتخاب و لینک را وارد کنید.",
                    "گروه را به‌روزرسانی (Update) کنید.",
                    "یک کانفیگ را انتخاب و Connect را بزنید.",
                ),
            ),
            AppGuide(
                key="singbox",
                name="sing-box (SFA)",
                download_url="https://play.google.com/store/apps/details?id=io.nekohasekai.sfa",
                steps=(
                    "اپ sing-box را از گوگل‌پلی نصب کنید.",
                    "لینک اشتراک را از ربات دریافت و کپی کنید.",
                    "در sing-box به Profiles بروید و + را بزنید.",
                    "Remote / Subscription را انتخاب و لینک را Paste کنید.",
                    "پروفایل را ذخیره و Update کنید.",
                    "پروفایل را فعال و دکمه Start را بزنید.",
                ),
            ),
        ),
    ),
    PlatformGuide(
        key="ios",
        name="آیفون / iOS",
        emoji="🍎",
        apps=(
            AppGuide(
                key="happ",
                name="Happ",
                download_url="https://apps.apple.com/app/happ-proxy-utility/id6504287215",
                steps=(
                    "Happ را از App Store نصب کنید.",
                    "لینک اشتراک را از ربات در بخش «اشتراک‌های من» کپی کنید.",
                    "Happ را باز کنید و دکمه + را بزنید.",
                    "گزینه «افزودن اشتراک» یا Import from Clipboard را انتخاب کنید.",
                    "لینک اشتراک را Paste کنید یا از کلیپ‌بورد وارد کنید.",
                    "پس از لود سرورها، یکی را انتخاب کنید.",
                    "دکمه اتصال را بزنید و اجازه نصب VPN Configuration را بدهید.",
                ),
            ),
            AppGuide(
                key="streisand",
                name="Streisand",
                download_url="https://apps.apple.com/app/streisand/id6450534064",
                steps=(
                    "Streisand را از App Store نصب کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "Streisand را باز کنید و + را بزنید.",
                    "گزینه Add from URL یا Import from clipboard را انتخاب کنید.",
                    "لینک اشتراک را وارد یا Paste کنید.",
                    "پس از لود شدن سرورها، یکی را انتخاب و Connect را بزنید.",
                    "در صورت درخواست، اجازه افزودن VPN Profile را بدهید.",
                ),
            ),
            AppGuide(
                key="hiddify",
                name="Hiddify",
                download_url="https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532",
                steps=(
                    "Hiddify را از App Store نصب کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "در Hiddify گزینه افزودن اشتراک (+) را بزنید.",
                    "لینک را Paste کنید یا از کلیپ‌بورد وارد کنید.",
                    "پروفایل را انتخاب و Connect را بزنید.",
                    "اجازه نصب VPN Configuration را تأیید کنید.",
                ),
            ),
            AppGuide(
                key="v2box",
                name="V2Box",
                download_url="https://apps.apple.com/app/v2box/id6446814690",
                steps=(
                    "V2Box را از App Store نصب کنید.",
                    "لینک اشتراک را از ربات دریافت کنید.",
                    "در V2Box به تب Configs بروید و + را بزنید.",
                    "Import v2ray uri from clipboard یا Add subscription URL را انتخاب کنید.",
                    "لینک را وارد و Subscribe/Update را بزنید.",
                    "یک کانفیگ را انتخاب و اتصال را فعال کنید.",
                ),
            ),
        ),
    ),
    PlatformGuide(
        key="mac",
        name="مک / macOS",
        emoji="💻",
        apps=(
            AppGuide(
                key="hiddify",
                name="Hiddify",
                download_url="https://github.com/hiddify/hiddify-next/releases",
                steps=(
                    "نسخه macOS را از لینک دانلود بگیرید و نصب کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "Hiddify را باز کنید و Add Subscription را بزنید.",
                    "لینک را Paste کنید و ذخیره کنید.",
                    "پروفایل را انتخاب و Connect را بزنید.",
                    "در صورت نیاز اجازه افزودن VPN را در System Settings بدهید.",
                ),
            ),
            AppGuide(
                key="v2rayu",
                name="V2rayU",
                download_url="https://github.com/yanue/V2rayU/releases",
                steps=(
                    "V2rayU را از GitHub دانلود و به Programs بکشید.",
                    "از ربات لینک اشتراک را کپی کنید.",
                    "V2rayU را باز کنید؛ از منو Server > Import از clipboard یا Subscribe.",
                    "لینک اشتراک را وارد و Subscribe کنید.",
                    "یک سرور را انتخاب و Turn On را بزنید.",
                ),
            ),
            AppGuide(
                key="clashverge",
                name="Clash Verge Rev",
                download_url="https://github.com/clash-verge-rev/clash-verge-rev/releases",
                steps=(
                    "Clash Verge Rev را برای macOS دانلود و نصب کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "در برنامه به Profiles بروید و New را بزنید.",
                    "لینک Subscription را Paste و Import کنید.",
                    "پروفایل را فعال و حالت System Proxy یا TUN را روشن کنید.",
                    "یک نود را انتخاب و اتصال را شروع کنید.",
                ),
            ),
            AppGuide(
                key="singbox",
                name="sing-box (macOS)",
                download_url="https://apps.apple.com/app/sing-box/id6451272670",
                steps=(
                    "sing-box را از Mac App Store نصب کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "در Profiles روی + بزنید و Remote subscription را انتخاب کنید.",
                    "لینک را وارد و پروفایل را Update کنید.",
                    "پروفایل را Start کنید.",
                ),
            ),
        ),
    ),
    PlatformGuide(
        key="win",
        name="ویندوز",
        emoji="🪟",
        apps=(
            AppGuide(
                key="hiddify",
                name="Hiddify",
                download_url="https://github.com/hiddify/hiddify-next/releases",
                steps=(
                    "نسخه Windows را از لینک دانلود نصب کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "Hiddify را اجرا و Add Subscription را بزنید.",
                    "لینک را Paste و ذخیره کنید.",
                    "پروفایل را انتخاب و Connect را بزنید.",
                ),
            ),
            AppGuide(
                key="v2rayn",
                name="v2rayN",
                download_url="https://github.com/2dust/v2rayN/releases",
                steps=(
                    "v2rayN را از GitHub دانلود و اجرا کنید (نیاز به .NET در برخی نسخه‌ها).",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "در v2rayN از منو Subscription > Subscription settings > Add.",
                    "لینک را در URL قرار دهید و Update subscription را بزنید.",
                    "یک سرور را انتخاب و Enter یا راست‌کلیک > Set as active server.",
                    "از منو System proxy یا Enable Tun را فعال کنید.",
                ),
            ),
            AppGuide(
                key="nekoray",
                name="Nekoray",
                download_url="https://github.com/MatsuriDayo/nekoray/releases",
                steps=(
                    "Nekoray را از GitHub دانلود و اجرا کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "در Program > Preferences > Groups یک گروه Subscription بسازید.",
                    "لینک را اضافه و Update کنید.",
                    "یک کانفیگ را انتخاب و Start را بزنید.",
                ),
            ),
            AppGuide(
                key="clashverge",
                name="Clash Verge Rev",
                download_url="https://github.com/clash-verge-rev/clash-verge-rev/releases",
                steps=(
                    "Clash Verge Rev را برای Windows نصب کنید.",
                    "لینک اشتراک را از ربات کپی کنید.",
                    "در Profiles پروفایل جدید با لینک Subscription بسازید.",
                    "پروفایل را فعال و System Proxy را روشن کنید.",
                    "نود مناسب را انتخاب کنید.",
                ),
            ),
        ),
    ),
)

_PLATFORM_BY_KEY = {platform.key: platform for platform in PLATFORMS}


def get_platform(platform_key: str) -> PlatformGuide | None:
    return _PLATFORM_BY_KEY.get(platform_key)


def get_app(platform_key: str, app_key: str) -> AppGuide | None:
    platform = get_platform(platform_key)
    if platform is None:
        return None
    for app in platform.apps:
        if app.key == app_key:
            return app
    return None


def guides_home_text(*, extra_note: str = "") -> str:
    lines = [
        "راهنمای اتصال",
        "",
        "ابتدا سیستم‌عامل خود را انتخاب کنید.",
        "سپس اپ مورد نظر را بزنید تا مراحل نصب و اتصال را ببینید.",
        "",
        "لینک اشتراک را از «اشتراک‌های من» > «لینک اشتراک» در همین ربات بگیرید.",
    ]
    note = extra_note.strip()
    if note and note != "آموزش اتصال به زودی اضافه می‌شود.":
        lines.extend(["", note])
    return "\n".join(lines)


def guides_platform_text(platform: PlatformGuide) -> str:
    return "\n".join(
        [
            f"{platform.emoji} راهنمای {platform.name}",
            "",
            "اپ مورد نظر خود را انتخاب کنید:",
        ]
    )


def guides_app_text(platform: PlatformGuide, app: AppGuide) -> str:
    step_lines = [f"{index}. {step}" for index, step in enumerate(app.steps, start=1)]
    return "\n".join(
        [
            f"{platform.emoji} {platform.name} — {app.name}",
            "",
            "مراحل اتصال:",
            *step_lines,
            "",
            "اگر لینک اشتراک را ندارید، از منوی اصلی به «اشتراک‌های من» بروید.",
        ]
    )


def guides_platforms_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{platform.emoji} {platform.name}", callback_data=f"guide:p:{platform.key}")]
        for platform in PLATFORMS
    ]
    rows.append([InlineKeyboardButton(text=c.BACK, callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def guides_apps_keyboard(platform: PlatformGuide) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=app.name, callback_data=f"guide:a:{platform.key}:{app.key}")]
        for app in platform.apps
    ]
    rows.append(
        [
            InlineKeyboardButton(text=c.BACK, callback_data="menu:tutorial"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def guides_app_keyboard(platform: PlatformGuide, app: AppGuide) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬇️ دانلود اپ", url=app.download_url)],
            [InlineKeyboardButton(text=c.BACK, callback_data=f"guide:p:{platform.key}")],
            [InlineKeyboardButton(text="سیستم‌عامل‌ها", callback_data="menu:tutorial")],
        ]
    )
