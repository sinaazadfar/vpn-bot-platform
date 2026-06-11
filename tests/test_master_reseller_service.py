from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine
from vpn_bot_platform.common.models import ResellerStatus, SellerBotRuntimeType
from vpn_bot_platform.master_bot.services.resellers import ResellerService


@pytest.mark.asyncio
async def test_register_reseller_and_seller_bot() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        registered = await service.register_reseller(
            telegram_id=12345,
            display_name="Test Reseller",
        )
        seller_bot = await service.register_seller_bot(
            reseller_telegram_id=12345,
            bot_name="test_bot",
            bot_token="123:secret",
        )
        panel = await service.register_marzban_panel(
            name="main-panel",
            base_url="https://panel.example.com/",
            token="panel-token",
        )
        assignment = await service.assign_panel(
            reseller_telegram_id=12345,
            panel_id=panel.id,
            marzban_admin_username="reseller_admin",
        )
        renamed = await service.rename_reseller(
            reseller_telegram_id=12345,
            display_name="Renamed Reseller",
            actor_telegram_id=999,
        )
        disabled = await service.set_reseller_status(
            reseller_telegram_id=12345,
            status=ResellerStatus.DISABLED,
            actor_telegram_id=999,
        )
        template = await service.register_external_bot_template(
            key="marzbot-free",
            name="Marzbot Free",
            repo_url="https://github.com/govfvck/Marzbot-free",
            ref="main",
            local_path="external/seller-bots/marzbot-free",
            license_name="AGPL-3.0",
            runtime_adapter="manual",
            actor_telegram_id=999,
        )
        external_seller_bot = await service.register_external_seller_bot(
            reseller_telegram_id=12345,
            bot_name="external-test",
            bot_token="456:secret",
            template_id_or_key="marzbot-free",
            actor_telegram_id=999,
        )
        templates = await service.list_external_bot_templates()
    finally:
        await dispose_engine()

    assert registered.existed is False
    assert registered.reseller.telegram_user_id == 12345
    assert seller_bot.reseller_id == registered.reseller.id
    assert seller_bot.token_encrypted != "123:secret"
    assert panel.base_url == "https://panel.example.com"
    assert panel.token_encrypted != "panel-token"
    assert assignment.reseller_id == registered.reseller.id
    assert assignment.panel_id == panel.id
    assert renamed.display_name == "Renamed Reseller"
    assert disabled.status == "disabled"
    assert template.key == "marzbot-free"
    assert templates[0].id == template.id
    assert external_seller_bot.external_template_id == template.id
    assert external_seller_bot.runtime_type == SellerBotRuntimeType.EXTERNAL_TEMPLATE.value
