from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine
from vpn_bot_platform.master_bot.services.resellers import ResellerService


@pytest.mark.asyncio
async def test_provision_seller_bot_with_password_panel() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        result = await service.provision_seller_bot_with_password_panel(
            reseller_telegram_id=12345,
            reseller_display_name="Admin 12345",
            bot_name="seller-one",
            bot_token="123:secret",
            panel_name="main-panel",
            panel_base_url="https://panel.example.com/",
            panel_username="root",
            panel_password="secret",
            marzban_admin_username="seller_admin",
            volume_limit_gb=100,
            actor_telegram_id=999,
        )
    finally:
        await dispose_engine()

    assert result.reseller_existed is False
    assert result.reseller.telegram_user_id == 12345
    assert result.panel.base_url == "https://panel.example.com"
    assert result.panel.username_encrypted != "root"
    assert result.panel.password_encrypted != "secret"
    assert result.seller_bot.name == "seller-one"
    assert result.seller_bot.token_encrypted != "123:secret"
    assert result.seller_bot.volume_limit_gb == 100
    assert result.assignment.panel_id == result.panel.id
    assert result.assignment.reseller_id == result.reseller.id
    assert result.assignment.marzban_admin_username == "seller_admin"
