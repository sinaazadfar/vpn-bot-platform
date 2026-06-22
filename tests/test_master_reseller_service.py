from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import create_all, dispose_engine, init_engine
from types import SimpleNamespace

from vpn_bot_platform.common.config import Settings
from vpn_bot_platform.common.models import (
    ResellerStatus,
    SellerBotRuntimeType,
    SellerBotUiProfile,
)
from vpn_bot_platform.master_bot.handlers.basic import master_menu_callback
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
            actor_telegram_id=999,
        )
        reseller = result.reseller
        panel = result.panel
        seller_bot = result.seller_bot
        assignment = result.assignment
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
        external_seller_bot, external_assignment = await service.register_external_seller_bot_with_panel(
            reseller_telegram_id=12345,
            bot_name="external-test",
            bot_token="456:secret",
            template_id_or_key="marzbot-free",
            panel_id=panel.id,
            marzban_admin_username="external_admin",
            actor_telegram_id=999,
        )
        simple_seller_bot, simple_seller_assignment = await service.register_seller_bot_with_panel(
            reseller_telegram_id=12345,
            bot_name="simple-seller-test",
            bot_token="654:secret",
            panel_id=panel.id,
            marzban_admin_username="simple_admin",
            ui_profile=SellerBotUiProfile.SIMPLE_SELLER,
            actor_telegram_id=999,
        )
        templates = await service.list_external_bot_templates()
        default_quota = await service.seller_bot_quota(seller_bot_id=seller_bot.id)
        added_quota = await service.add_seller_bot_volume(
            seller_bot_id=seller_bot.id,
            added_gb=100,
            actor_telegram_id=999,
        )
        second_added_quota = await service.add_seller_bot_volume(
            seller_bot_id=seller_bot.id,
            added_gb=50,
            actor_telegram_id=999,
        )
        audit_logs = await service.recent_audit_logs(limit=10)
    finally:
        await dispose_engine()

    assert result.reseller_existed is False
    assert reseller.telegram_user_id == 12345
    assert seller_bot.reseller_id == reseller.id
    assert seller_bot.volume_limit_gb == 0
    assert seller_bot.token_encrypted != "123:secret"
    assert panel.base_url == "https://panel.example.com"
    assert panel.password_encrypted != "secret"
    assert assignment.reseller_id == reseller.id
    assert assignment.panel_id == panel.id
    assert assignment.marzban_admin_username == "seller_admin"
    assert renamed.display_name == "Renamed Reseller"
    assert disabled.status == "disabled"
    assert template.key == "marzbot-free"
    assert {template.key for template in templates} == {"marzbot-free"}
    assert external_seller_bot.external_template_id == template.id
    assert external_seller_bot.runtime_type == SellerBotRuntimeType.EXTERNAL_TEMPLATE.value
    assert simple_seller_bot.external_template_id is None
    assert simple_seller_bot.runtime_type == SellerBotRuntimeType.NATIVE.value
    assert simple_seller_bot.ui_profile == SellerBotUiProfile.SIMPLE_SELLER.value
    assert simple_seller_assignment.panel_id == panel.id
    assert simple_seller_assignment.marzban_admin_username == "simple_admin"
    assert external_assignment.panel_id == panel.id
    assert external_assignment.marzban_admin_username == "external_admin"
    assert default_quota.limit_gb == 0
    assert default_quota.remaining_gb == 0
    assert added_quota.limit_gb == 100
    assert added_quota.remaining_gb == 100
    assert second_added_quota.limit_gb == 150
    assert second_added_quota.remaining_gb == 150
    assert any(log.action == "seller_bot.volume_add" for log in audit_logs)


@pytest.mark.asyncio
async def test_master_confirm_creates_simple_seller_as_native_platform_bot() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))
    state = _FakeState(
        {
            "sellerbot_runtime_type": "native",
            "sellerbot_ui_profile": SellerBotUiProfile.SIMPLE_SELLER.value,
            "sellerbot_template_key": None,
            "sellerbot_reseller_telegram_id": 22222,
            "sellerbot_name": "Simple Seller Bot",
            "sellerbot_token": "222:secret",
            "sellerbot_panel_id": "",
            "sellerbot_panel_admin": "simple_admin",
            "sellerbot_volume_limit_gb": 25,
        }
    )

    try:
        registered = await service.register_reseller(
            telegram_id=22222,
            display_name="Simple Seller Admin",
        )
        panel = await service.register_marzban_panel(
            name="simple-panel",
            base_url="https://simple-panel.example.com/",
            token="panel-token",
        )
        state.data["sellerbot_panel_id"] = panel.id
        callback = _FakeCallback("m:sellerbot_create", user_id=999)

        await master_menu_callback(callback, state, service)  # type: ignore[arg-type]

        seller_bots = await service.list_seller_bots()
        assignments = await service.list_panel_assignments_for_reseller(
            reseller_id=registered.reseller.id,
        )
    finally:
        await dispose_engine()

    assert state.cleared is True
    assert callback.alerts == []
    assert callback.message.edited_text is not None
    assert "Seller Bot Registered" in callback.message.edited_text
    assert len(seller_bots) == 1
    seller_bot = seller_bots[0]
    assert seller_bot.runtime_type == SellerBotRuntimeType.NATIVE.value
    assert seller_bot.external_template_id is None
    assert seller_bot.ui_profile == SellerBotUiProfile.SIMPLE_SELLER.value
    assert seller_bot.reseller_id == registered.reseller.id
    assert seller_bot.volume_limit_gb == 25
    assert len(assignments) == 1
    assert assignments[0].assignment.panel_id == panel.id
    assert assignments[0].assignment.marzban_admin_username == "simple_admin"


@pytest.mark.asyncio
async def test_master_confirm_shows_error_when_seller_bot_create_fails() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))
    state = _FakeState(
        {
            "sellerbot_runtime_type": "native",
            "sellerbot_ui_profile": SellerBotUiProfile.SIMPLE_SELLER.value,
            "sellerbot_template_key": None,
            "sellerbot_reseller_telegram_id": 22222,
            "sellerbot_name": "Duplicate Simple Seller Bot",
            "sellerbot_token": "222:secret",
            "sellerbot_panel_id": "",
            "sellerbot_panel_admin": "simple_admin",
            "sellerbot_volume_limit_gb": 25,
        }
    )

    try:
        await service.register_reseller(
            telegram_id=22222,
            display_name="Simple Seller Admin",
        )
        await service.register_seller_bot(
            reseller_telegram_id=22222,
            bot_name="Existing Bot",
            bot_token="222:secret",
        )
        panel = await service.register_marzban_panel(
            name="simple-panel",
            base_url="https://simple-panel.example.com/",
            token="panel-token",
        )
        state.data["sellerbot_panel_id"] = panel.id
        callback = _FakeCallback("m:sellerbot_create", user_id=999)

        await master_menu_callback(callback, state, service)  # type: ignore[arg-type]

        seller_bots = await service.list_seller_bots()
    finally:
        await dispose_engine()

    assert state.cleared is False
    assert callback.alerts == ["seller_bot_token_already_registered"]
    assert callback.message.edited_text is not None
    assert "Confirm Seller Bot" in callback.message.edited_text
    assert "Stock: 25 GB" in callback.message.edited_text
    assert "Could not create seller bot: seller_bot_token_already_registered" in callback.message.edited_text
    assert len(seller_bots) == 1


@pytest.mark.asyncio
async def test_delete_seller_bot_soft_deletes_and_audits() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await service.register_reseller(telegram_id=22222, display_name="Seller Admin")
        seller_bot = await service.register_seller_bot(
            reseller_telegram_id=22222,
            bot_name="Delete Me",
            bot_token="333:secret",
            volume_limit_gb=10,
        )

        deleted = await service.delete_seller_bot(
            seller_bot_id=seller_bot.id,
            actor_telegram_id=999,
        )
        seller_bots = await service.list_seller_bots()
        audit_logs = await service.recent_audit_logs(limit=5)
    finally:
        await dispose_engine()

    assert deleted.id == seller_bot.id
    assert deleted.status == "disabled"
    assert deleted.container_id is None
    assert deleted.container_name is None
    assert deleted.last_error == "deleted by super user"
    assert [item.id for item in seller_bots] == [seller_bot.id]
    assert seller_bots[0].status == "disabled"
    assert any(log.action == "seller_bot.delete" and log.target_id == seller_bot.id for log in audit_logs)


@pytest.mark.asyncio
async def test_master_delete_seller_bot_callback_disables_bot() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await service.register_reseller(telegram_id=22222, display_name="Seller Admin")
        seller_bot = await service.register_seller_bot(
            reseller_telegram_id=22222,
            bot_name="Delete From UI",
            bot_token="444:secret",
            volume_limit_gb=10,
        )
        state = _FakeState({})
        confirm_callback = _FakeCallback(f"m:seller_delete_confirm:{seller_bot.id}", user_id=999)

        await master_menu_callback(confirm_callback, state, service)  # type: ignore[arg-type]

        apply_callback = _FakeCallback(f"m:seller_delete_apply:{seller_bot.id}", user_id=999)
        await master_menu_callback(apply_callback, state, service)  # type: ignore[arg-type]

        seller_bots = await service.list_seller_bots()
    finally:
        await dispose_engine()

    assert confirm_callback.message.edited_text is not None
    assert "Delete Seller Bot" in confirm_callback.message.edited_text
    confirm_callbacks = [
        button.callback_data
        for row in confirm_callback.message.reply_markup.inline_keyboard
        for button in row
    ]
    assert f"m:seller_delete_apply:{seller_bot.id}" in confirm_callbacks
    assert apply_callback.message.edited_text is not None
    assert "Seller Bot Deleted" in apply_callback.message.edited_text
    assert seller_bots[0].status == "disabled"


@pytest.mark.asyncio
async def test_start_simple_seller_uses_standalone_runtime_and_database_path() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    key = Fernet.generate_key().decode("utf-8")
    runtime = _FakeRuntimeController()
    service = ResellerService(
        SecretBox(key),
        settings=_settings(key),
        runtime_controller=runtime,
    )
    token = _valid_bot_token()

    try:
        registered = await service.register_reseller(telegram_id=22222, display_name="Simple Admin")
        panel = await service.register_marzban_panel(
            name="panel",
            base_url="https://panel.example.com",
            username="panel-user",
            password="panel-pass",
            token="panel-token",
        )
        seller_bot, _assignment = await service.register_seller_bot_with_panel(
            reseller_telegram_id=registered.reseller.telegram_user_id,
            bot_name="simple",
            bot_token=token,
            panel_id=panel.id,
            marzban_admin_username="marzban-admin",
            ui_profile=SellerBotUiProfile.SIMPLE_SELLER,
        )

        started = await service.start_seller_bot(seller_bot_id=seller_bot.id)
    finally:
        await dispose_engine()

    assert started.status == "running"
    assert runtime.started is not None
    assert runtime.started["command"] == ["python", "-m", "bot"]
    env = runtime.started["environment"]
    assert env["BOT_TOKEN"] == token
    assert env["SELLER_BOT_ID"] == seller_bot.id
    assert env["DATABASE_PATH"] == f"/app/data/sellers/{seller_bot.id}/bot.sqlite3"
    assert env["SELLER_DATABASE_PATH"] == f"/app/data/sellers/{seller_bot.id}/bot.sqlite3"
    assert env["PLATFORM_DATABASE_URL"] == "sqlite+aiosqlite:///:memory:"
    assert env["ADMIN_IDS"] == "22222"
    assert env["MARZBAN_BASE_URL"] == "https://panel.example.com"
    assert env["MARZBAN_USERNAME"] == "panel-user"
    assert env["MARZBAN_PASSWORD"] == "panel-pass"
    assert env["MARZBAN_TOKEN"] == "panel-token"
    assert "DATABASE_URL" not in env


@pytest.mark.asyncio
async def test_start_platform_seller_keeps_platform_runtime() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    key = Fernet.generate_key().decode("utf-8")
    runtime = _FakeRuntimeController()
    service = ResellerService(
        SecretBox(key),
        settings=_settings(key),
        runtime_controller=runtime,
    )
    token = _valid_bot_token()

    try:
        await service.register_reseller(telegram_id=33333, display_name="Platform Admin")
        seller_bot = await service.register_seller_bot(
            reseller_telegram_id=33333,
            bot_name="platform",
            bot_token=token,
            ui_profile=SellerBotUiProfile.PLATFORM,
        )

        await service.start_seller_bot(seller_bot_id=seller_bot.id)
    finally:
        await dispose_engine()

    assert runtime.started is not None
    assert runtime.started["command"] == ["python", "-m", "vpn_bot_platform.seller_bot.main"]
    env = runtime.started["environment"]
    assert env["SELLER_BOT_TOKEN"] == token
    assert env["SELLER_BOT_ID"] == seller_bot.id
    assert env["DATABASE_URL"] == "sqlite+aiosqlite:///:memory:"
    assert "DATABASE_PATH" not in env


@pytest.mark.asyncio
async def test_seller_bot_admin_contact_returns_owner_telegram_id() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await service.register_reseller(telegram_id=44444, display_name="Seller Admin")
        seller_bot = await service.register_seller_bot(
            reseller_telegram_id=44444,
            bot_name="seller",
            bot_token="123456:" + ("B" * 35),
        )

        contact = await service.seller_bot_admin_contact(seller_bot_id=seller_bot.id)
    finally:
        await dispose_engine()

    assert contact.seller_bot.id == seller_bot.id
    assert contact.admin_telegram_id == 44444


class _FakeState:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.state = state

    async def clear(self) -> None:
        self.cleared = True
        self.data.clear()


class _FakeMessage:
    def __init__(self) -> None:
        self.edited_text: str | None = None
        self.reply_markup = None

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edited_text = text
        self.reply_markup = kwargs.get("reply_markup")


class _FakeCallback:
    def __init__(self, data: str, *, user_id: int) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _FakeMessage()
        self.alerts: list[str] = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        if text:
            self.alerts.append(text)


class _FakeRuntimeController:
    def __init__(self) -> None:
        self.started: dict | None = None

    def start_seller(
        self,
        *,
        seller_bot_id: str,
        environment: dict[str, str],
        container_id: str | None = None,
        command: list[str] | None = None,
    ) -> str:
        self.started = {
            "seller_bot_id": seller_bot_id,
            "environment": environment,
            "container_id": container_id,
            "command": command,
        }
        return "container-123"

    def stop_seller(self, *, container_id: str | None) -> None:
        return None

    def seller_logs(self, *, container_id: str | None, tail: int = 120) -> str:
        return ""

    def seller_health(self, *, container_id: str | None) -> str:
        return "running"


def _settings(fernet_key: str) -> Settings:
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        FERNET_KEY=fernet_key,
        SELLER_DATA_HOST_PATH="/tmp/sellers",
    )


def _valid_bot_token() -> str:
    return "123456:" + ("A" * 35)
