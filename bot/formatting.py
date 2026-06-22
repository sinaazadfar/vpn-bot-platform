from html import escape

MESSAGE_FOOTER = "\n\n\n➖➖➖"


def with_footer(text: str) -> str:
    if text.endswith(MESSAGE_FOOTER):
        return text
    return f"{text}{MESSAGE_FOOTER}"


def html_code(value: str) -> str:
    return f"<code>{escape(value, quote=False)}</code>"


def html_link(label: str, url: str) -> str:
    return f'<a href="{escape(url, quote=True)}">{escape(label, quote=False)}</a>'


def html_pre(value: str) -> str:
    return f"<pre>{escape(value, quote=False)}</pre>"
