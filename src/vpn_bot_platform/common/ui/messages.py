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


def title(text: str) -> str:
    return f"{text}\n" + ("-" * min(len(text), 32))


def section(name: str, rows: list[str]) -> str:
    if not rows:
        rows = ["- none"]
    return "\n".join([name, *rows])


def status_label(status: str | None) -> str:
    normalized = (status or "unknown").lower()
    icon = STATUS_ICON.get(normalized, "[?]")
    return f"{icon} {normalized.replace('_', ' ').title()}"


def short_id(value: str | None, *, size: int = 8) -> str:
    if not value:
        return "-"
    return value if len(value) <= size else value[:size]
