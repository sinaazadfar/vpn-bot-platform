from __future__ import annotations


STATUS_ICON = {
    "active": "[OK]",
    "running": "[RUN]",
    "completed": "[OK]",
    "approved": "[OK]",
    "paid": "[OK]",
    "pending": "[...]",
    "pending_payment": "[...]",
    "waiting_payment": "[...]",
    "waiting_approval": "[...]",
    "provisioning": "[...]",
    "suspended": "[PAUSE]",
    "stopped": "[STOP]",
    "disabled": "[OFF]",
    "error": "[ERR]",
    "failed": "[ERR]",
    "canceled": "[X]",
    "rejected": "[X]",
}

STATUS_TEXT = {
    "active": "فعال",
    "running": "در حال اجرا",
    "completed": "تکمیل شده",
    "approved": "تایید شده",
    "paid": "پرداخت شده",
    "pending": "در انتظار",
    "pending_payment": "در انتظار پرداخت",
    "waiting_payment": "در انتظار پرداخت",
    "waiting_approval": "در انتظار تایید",
    "provisioning": "در حال ساخت سرویس",
    "suspended": "تعلیق شده",
    "stopped": "متوقف",
    "disabled": "غیرفعال",
    "error": "خطا",
    "failed": "ناموفق",
    "canceled": "لغو شده",
    "rejected": "رد شده",
    "draft": "پیش نویس",
    "sent": "ارسال شده",
    "open": "باز",
    "closed": "بسته",
}


def title(text: str) -> str:
    return f"{text}\n" + ("-" * min(len(text), 32))


def section(name: str, rows: list[str]) -> str:
    if not rows:
        rows = ["- موردی وجود ندارد"]
    return "\n".join([name, *rows])


def status_label(status: str | None) -> str:
    normalized = (status or "unknown").lower()
    icon = STATUS_ICON.get(normalized, "[?]")
    label = STATUS_TEXT.get(normalized, normalized.replace("_", " "))
    return f"{icon} {label}"


def short_id(value: str | None, *, size: int = 8) -> str:
    if not value:
        return "-"
    return value if len(value) <= size else value[:size]
