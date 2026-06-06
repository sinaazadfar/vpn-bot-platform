from __future__ import annotations

from vpn_bot_platform.integrations.docker_runtime import seller_container_name


def test_seller_container_name_is_stable() -> None:
    assert seller_container_name("abc-123") == "seller-abc-123"

