import base64

from bot.configs import build_configs_txt, parse_v2ray_configs


def test_parse_plaintext_v2ray_configs():
    raw = "\n".join(
        [
            "vless://one",
            "vmess://two",
            "trojan://three",
        ]
    )

    assert parse_v2ray_configs(raw, "https://sub.example") == [
        "vless://one",
        "vmess://two",
        "trojan://three",
    ]


def test_parse_base64_subscription_configs():
    raw_configs = "vless://one\nss://two\nhysteria2://three"
    encoded = base64.b64encode(raw_configs.encode("utf-8")).decode("ascii")

    assert parse_v2ray_configs(encoded, "https://sub.example") == [
        "vless://one",
        "ss://two",
        "hysteria2://three",
    ]


def test_parse_ignores_unsupported_lines_and_deduplicates():
    raw = "hello\nvless://one\nnot-a-config\nvless://one\ntuic://two"

    assert parse_v2ray_configs(raw, "https://sub.example") == [
        "vless://one",
        "tuic://two",
    ]


def test_parse_falls_back_to_subscription_url():
    assert parse_v2ray_configs("not configs", "https://sub.example") == ["https://sub.example"]
    assert parse_v2ray_configs("", "https://sub.example") == ["https://sub.example"]


def test_build_configs_txt_includes_subscription_and_configs():
    text = build_configs_txt("https://sub.example", ["vless://one", "vmess://two"])

    assert "Subscription link:\nhttps://sub.example" in text
    assert "Configs:\nvless://one\nvmess://two" in text
