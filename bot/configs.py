from __future__ import annotations

import base64
import binascii

CONFIG_PREFIXES = (
    "vless://",
    "vmess://",
    "trojan://",
    "ss://",
    "ssr://",
    "tuic://",
    "hysteria://",
    "hysteria2://",
)


def parse_v2ray_configs(raw_text: str, subscription_url: str) -> list[str]:
    candidates = [raw_text]
    decoded = _try_decode_base64(raw_text)
    if decoded:
        candidates.append(decoded)

    configs: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        for line in candidate.replace("\r", "\n").split("\n"):
            config = line.strip()
            if _is_config_link(config) and config not in seen:
                configs.append(config)
                seen.add(config)
    return configs or [subscription_url]


def build_configs_txt(subscription_url: str, configs: list[str]) -> str:
    lines = [
        "Subscription link:",
        subscription_url,
        "",
        "Configs:",
    ]
    lines.extend(configs or [subscription_url])
    return "\n".join(lines) + "\n"


def _is_config_link(value: str) -> bool:
    lowered = value.lower()
    return any(lowered.startswith(prefix) for prefix in CONFIG_PREFIXES)


def _try_decode_base64(value: str) -> str | None:
    compact = "".join(value.split())
    if not compact:
        return None
    padding = "=" * (-len(compact) % 4)
    try:
        decoded = base64.b64decode(compact + padding, validate=False)
        text = decoded.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    return text if any(prefix in text.lower() for prefix in CONFIG_PREFIXES) else None
