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
from vpn_bot_platform.seller_bot.services import SellerContextService


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
    state = _FakeState(_bundle_wizard_state())
    callback = _FakeCallback("m:sellerbot_create", user_id=999)

    try:
        await master_menu_callback(callback, state, service)  # type: ignore[arg-type]

        seller_bots = await service.list_seller_bots()
        resellers = await service.list_resellers()
        assignments = await service.list_panel_assignments_for_reseller(
            reseller_id=seller_bots[0].reseller_id,
        )
        audit_logs = await service.recent_audit_logs(limit=10)
    finally:
        await dispose_engine()

    assert state.cleared is True
    assert callback.alerts == []
    assert callback.message.edited_text is not None
    assert "Seller Bot Provisioned" in callback.message.edited_text
    assert len(seller_bots) == 1
    seller_bot = seller_bots[0]
    assert seller_bot.runtime_type == SellerBotRuntimeType.NATIVE.value
    assert seller_bot.external_template_id is None
    assert seller_bot.ui_profile == SellerBotUiProfile.SIMPLE_SELLER.value
    assert resellers[0].telegram_user_id == 22222
    assert seller_bot.volume_limit_gb == 25
    assert len(assignments) == 1
    assert assignments[0].assignment.marzban_admin_username == "simple_admin"
    assert any(log.action == "seller_bot.provision_bundle" for log in audit_logs)


@pytest.mark.asyncio
async def test_master_confirm_shows_error_when_reseller_already_exists() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))
    token = _valid_bot_token()

    try:
        await service.provision_seller_bot_bundle(
            reseller_telegram_id=22222,
            reseller_display_name="Existing Owner",
            bot_name="Existing Bot",
            bot_token=token,
            panel_name="existing-panel",
            panel_base_url="https://existing-panel.example.com",
            panel_token="panel-token",
            marzban_admin_username="simple_admin",
            ui_profile=SellerBotUiProfile.SIMPLE_SELLER,
            volume_limit_gb=10,
            actor_telegram_id=999,
        )
        state = _FakeState(
            _bundle_wizard_state(
                sellerbot_token=_valid_bot_token() + "B",
                sellerbot_panel_base_url="https://another-panel.example.com",
            )
        )
        callback = _FakeCallback("m:sellerbot_create", user_id=999)

        await master_menu_callback(callback, state, service)  # type: ignore[arg-type]

        seller_bots = await service.list_seller_bots()
    finally:
        await dispose_engine()

    assert state.cleared is False
    assert callback.alerts == ["This Telegram ID already owns a reseller account."]
    assert callback.message.edited_text is not None
    assert "تأیید ربات جدید" in callback.message.edited_text
    assert "Could not create seller bot:" in callback.message.edited_text
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
    assert env["ADMIN_IDS"] == "22222,999"
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


@pytest.mark.asyncio
async def test_register_marzban_panel_rejects_duplicate_base_url() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await service.register_marzban_panel(
            name="panel-a",
            base_url="https://panel.example.com/",
            token="token-a",
        )
        with pytest.raises(ValueError, match="panel_base_url_exists"):
            await service.register_marzban_panel(
                name="panel-b",
                base_url="https://panel.example.com",
                username="admin",
                password="secret",
            )
    finally:
        await dispose_engine()


@pytest.mark.asyncio
async def test_update_panel_password_changes_encrypted_value() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    secret_box = SecretBox(Fernet.generate_key().decode("utf-8"))
    service = ResellerService(secret_box)

    try:
        panel = await service.register_marzban_panel(
            name="login-panel",
            base_url="https://login-panel.example.com",
            username="admin",
            password="old-secret",
        )
        old_encrypted = panel.password_encrypted
        detail = await service.update_panel_password(panel_id=panel.id, password="new-secret")
        updated_password = secret_box.decrypt(detail.panel.password_encrypted)
    finally:
        await dispose_engine()

    assert old_encrypted != detail.panel.password_encrypted
    assert updated_password == "new-secret"


@pytest.mark.asyncio
async def test_provision_seller_bot_bundle_creates_all_entities() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))
    token = _valid_bot_token()

    try:
        result = await service.provision_seller_bot_bundle(
            reseller_telegram_id=44444,
            reseller_display_name="Bundle Owner",
            bot_name="bundle-bot",
            bot_token=token,
            panel_name="bundle-panel",
            panel_base_url="https://bundle-panel.example.com",
            panel_username="admin",
            panel_password="secret",
            marzban_admin_username="marzban-admin",
            ui_profile=SellerBotUiProfile.PLATFORM,
            volume_limit_gb=50,
            actor_telegram_id=999,
        )
        resellers = await service.list_resellers()
        panels = await service.list_marzban_panels()
        seller_bots = await service.list_seller_bots()
        assignments = await service.list_panel_assignments_for_reseller(
            reseller_id=result.reseller.id,
        )
        audit_logs = await service.recent_audit_logs(limit=10)
    finally:
        await dispose_engine()

    assert result.reseller_existed is False
    assert len(resellers) == 1
    assert len(panels) == 1
    assert len(seller_bots) == 1
    assert len(assignments) == 1
    assert assignments[0].assignment.panel_id == result.panel.id
    assert seller_bots[0].volume_limit_gb == 50
    assert any(log.action == "seller_bot.provision_bundle" for log in audit_logs)


@pytest.mark.asyncio
async def test_provision_seller_bot_bundle_rejects_duplicate_reseller() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await service.provision_seller_bot_bundle(
            reseller_telegram_id=55555,
            reseller_display_name="First Owner",
            bot_name="first-bot",
            bot_token=_valid_bot_token(),
            panel_name="first-panel",
            panel_base_url="https://first-panel.example.com",
            panel_token="panel-token",
            actor_telegram_id=999,
        )
        with pytest.raises(ValueError, match="reseller_already_exists"):
            await service.provision_seller_bot_bundle(
                reseller_telegram_id=55555,
                reseller_display_name="Second Owner",
                bot_name="second-bot",
                bot_token=_valid_bot_token() + "C",
                panel_name="second-panel",
                panel_base_url="https://second-panel.example.com",
                panel_token="panel-token-2",
                actor_telegram_id=999,
            )
    finally:
        await dispose_engine()


@pytest.mark.asyncio
async def test_provision_seller_bot_bundle_rejects_duplicate_panel_url() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        await service.provision_seller_bot_bundle(
            reseller_telegram_id=66666,
            reseller_display_name="Owner A",
            bot_name="bot-a",
            bot_token=_valid_bot_token(),
            panel_name="shared-panel",
            panel_base_url="https://shared-panel.example.com/",
            panel_token="panel-token",
            actor_telegram_id=999,
        )
        with pytest.raises(ValueError, match="panel_base_url_exists"):
            await service.provision_seller_bot_bundle(
                reseller_telegram_id=77777,
                reseller_display_name="Owner B",
                bot_name="bot-b",
                bot_token=_valid_bot_token() + "D",
                panel_name="shared-panel-copy",
                panel_base_url="https://shared-panel.example.com",
                panel_token="panel-token-2",
                actor_telegram_id=999,
            )
    finally:
        await dispose_engine()


@pytest.mark.asyncio
async def test_platform_seller_super_user_passes_admin_check() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    key = Fernet.generate_key().decode("utf-8")
    settings = _settings(key, super_user_telegram_id=88888)
    service = ResellerService(SecretBox(key), settings=settings)

    try:
        result = await service.provision_seller_bot_bundle(
            reseller_telegram_id=33333,
            reseller_display_name="Platform Owner",
            bot_name="platform-bot",
            bot_token=_valid_bot_token(),
            panel_name="platform-panel",
            panel_base_url="https://platform-panel.example.com",
            panel_token="panel-token",
            ui_profile=SellerBotUiProfile.PLATFORM,
            actor_telegram_id=88888,
        )
        seller_context = SellerContextService(result.seller_bot.id, settings=settings)
        assert await seller_context.is_reseller_admin(telegram_id=88888) is True
        assert await seller_context.is_reseller_admin(telegram_id=33333) is True
        assert await seller_context.is_reseller_admin(telegram_id=11111) is False
    finally:
        await dispose_engine()


@pytest.mark.asyncio
async def test_simple_seller_admin_ids_include_super_user() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    key = Fernet.generate_key().decode("utf-8")
    settings = _settings(key, super_user_telegram_id=88888)
    service = ResellerService(SecretBox(key), settings=settings)

    admin_ids = service._simple_seller_admin_ids(33333)
    assert admin_ids == "33333,88888"


@pytest.mark.asyncio
async def test_change_seller_bot_panel_replaces_primary_assignment() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))
    token = _valid_bot_token()

    try:
        result = await service.provision_seller_bot_bundle(
            reseller_telegram_id=88881,
            reseller_display_name="Panel Change Owner",
            reseller_username="panel_owner",
            bot_name="panel-change-bot",
            bot_token=token,
            panel_name="old-panel",
            panel_base_url="https://old-panel.example.com",
            panel_token="old-token",
            ui_profile=SellerBotUiProfile.PLATFORM,
            actor_telegram_id=999,
        )
        new_panel = await service.register_marzban_panel(
            name="new-panel",
            base_url="https://new-panel.example.com",
            token="new-token",
        )
        summary = await service.change_seller_bot_panel(
            seller_bot_id=result.seller_bot.id,
            panel_id=new_panel.id,
            marzban_admin_username="new_admin",
            actor_telegram_id=999,
        )
        assignments = await service.list_panel_assignments_for_reseller(
            reseller_id=result.reseller.id,
        )
        audit_logs = await service.recent_audit_logs(limit=10)
    finally:
        await dispose_engine()

    assert summary.panel.id == new_panel.id
    assert summary.assignment.marzban_admin_username == "new_admin"
    assert len(assignments) == 1
    assert assignments[0].panel.id == new_panel.id
    assert any(log.action == "seller_bot.panel_change" for log in audit_logs)


@pytest.mark.asyncio
async def test_change_seller_bot_panel_rejects_same_panel() -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all()
    service = ResellerService(SecretBox(Fernet.generate_key().decode("utf-8")))

    try:
        result = await service.provision_seller_bot_bundle(
            reseller_telegram_id=88882,
            reseller_display_name="Same Panel Owner",
            reseller_username="same_panel",
            bot_name="same-panel-bot",
            bot_token=_valid_bot_token(),
            panel_name="only-panel",
            panel_base_url="https://only-panel.example.com",
            panel_token="only-token",
            actor_telegram_id=999,
        )
        with pytest.raises(ValueError, match="panel_already_assigned"):
            await service.change_seller_bot_panel(
                seller_bot_id=result.seller_bot.id,
                panel_id=result.panel.id,
                actor_telegram_id=999,
            )
    finally:
        await dispose_engine()


def _settings(fernet_key: str, *, super_user_telegram_id: int | None = 999) -> Settings:
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        FERNET_KEY=fernet_key,
        SELLER_DATA_HOST_PATH="/tmp/sellers",
        SUPER_USER_TELEGRAM_ID=super_user_telegram_id,
    )


def _bundle_wizard_state(**overrides) -> dict:
    state = {
        "sellerbot_ui_profile": SellerBotUiProfile.SIMPLE_SELLER.value,
        "sellerbot_owner_telegram_id": 22222,
        "sellerbot_owner_username": "simple_admin",
        "sellerbot_owner_display_name": "Simple Seller Admin",
        "sellerbot_name": "Simple Seller Bot",
        "sellerbot_token": _valid_bot_token(),
        "sellerbot_panel_name": "simple-panel",
        "sellerbot_panel_base_url": "https://simple-panel.example.com",
        "sellerbot_panel_auth": "token",
        "sellerbot_panel_token": "panel-token",
        "sellerbot_panel_admin": "simple_admin",
        "sellerbot_volume_limit_gb": 25,
    }
    state.update(overrides)
    return state


def _valid_bot_token() -> str:
    return "123456:" + ("A" * 35)
