from __future__ import annotations

import os
from dataclasses import dataclass
import datetime as dt

from vpn_bot_platform.common.config import Settings
from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import session_scope
from vpn_bot_platform.common.forced_join import (
    FORCED_JOIN_CHATS_KEY,
    ForcedJoinChat,
    decode_forced_join_chats,
    encode_forced_join_chats,
)
from vpn_bot_platform.common.repositories import (
    assign_panel_to_reseller,
    create_discount_code,
    create_global_broadcast,
    create_marzban_panel,
    create_plan,
    create_reseller,
    create_seller_bot,
    get_marzban_panel,
    get_global_broadcast,
    get_global_setting,
    global_sales_report,
    get_reseller_by_telegram_id,
    get_seller_bot,
    list_all_plans,
    list_discount_codes,
    list_pending_broadcast_recipients,
    mark_broadcast_sent,
    record_audit_log,
    set_global_setting,
    list_marzban_panels,
    list_resellers,
    update_seller_runtime_state,
    upsert_telegram_user,
)
from vpn_bot_platform.common.models import (
    AuditActorType,
    MarzbanPanel,
    Reseller,
    ResellerPanelAssignment,
    SellerBot,
    SellerBotStatus,
    Plan,
    DiscountCode,
    DiscountType,
    Broadcast,
    BroadcastRecipient,
)
from vpn_bot_platform.integrations.docker_runtime import seller_container_name
from vpn_bot_platform.integrations.runtime_controller import (
    DockerSellerRuntimeController,
    SellerRuntimeController,
)


@dataclass(frozen=True)
class RegisteredReseller:
    reseller: Reseller
    existed: bool


@dataclass(frozen=True)
class SellerRuntimeStatus:
    seller_bot: SellerBot
    health: str
    logs: str | None = None


@dataclass(frozen=True)
class BroadcastDraft:
    broadcast: Broadcast
    recipients: list[BroadcastRecipient]


class ResellerService:
    def __init__(
        self,
        secret_box: SecretBox,
        settings: Settings | None = None,
        runtime_controller: SellerRuntimeController | None = None,
    ) -> None:
        self.secret_box = secret_box
        self.settings = settings
        self.runtime_controller = runtime_controller

    async def register_reseller(
        self,
        *,
        telegram_id: int,
        display_name: str,
        username: str | None = None,
    ) -> RegisteredReseller:
        async with session_scope() as session:
            await upsert_telegram_user(
                session,
                telegram_id=telegram_id,
                username=username,
                first_name=display_name,
            )
            existing = await get_reseller_by_telegram_id(session, telegram_id=telegram_id)
            if existing is not None:
                return RegisteredReseller(reseller=existing, existed=True)
            reseller = await create_reseller(
                session,
                telegram_user_id=telegram_id,
                display_name=display_name,
            )
            await record_audit_log(
                session,
                action="reseller.create",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=None,
                reseller_id=reseller.id,
                target_type="reseller",
                target_id=reseller.id,
                metadata={"telegram_user_id": telegram_id, "display_name": display_name},
            )
            await session.flush()
            return RegisteredReseller(reseller=reseller, existed=False)

    async def register_seller_bot(
        self,
        *,
        reseller_telegram_id: int,
        bot_name: str,
        bot_token: str,
    ) -> SellerBot:
        async with session_scope() as session:
            reseller = await get_reseller_by_telegram_id(
                session,
                telegram_id=reseller_telegram_id,
            )
            if reseller is None:
                raise ValueError("reseller_not_found")
            seller_bot = await create_seller_bot(
                session,
                reseller_id=reseller.id,
                name=bot_name,
                token=bot_token,
                secret_box=self.secret_box,
            )
            await record_audit_log(
                session,
                action="seller_bot.register",
                actor_type=AuditActorType.SUPER_USER,
                reseller_id=reseller.id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={"reseller_telegram_id": reseller_telegram_id, "bot_name": bot_name},
            )
            await session.flush()
            return seller_bot

    async def list_resellers(self) -> list[Reseller]:
        async with session_scope() as session:
            return await list_resellers(session)

    async def register_marzban_panel(
        self,
        *,
        name: str,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
    ) -> MarzbanPanel:
        if not token and not (username and password):
            raise ValueError("panel_credentials_required")
        async with session_scope() as session:
            panel = await create_marzban_panel(
                session,
                name=name,
                base_url=base_url,
                username=username,
                password=password,
                token=token,
                secret_box=self.secret_box,
            )
            await record_audit_log(
                session,
                action="marzban_panel.create",
                actor_type=AuditActorType.SUPER_USER,
                target_type="marzban_panel",
                target_id=panel.id,
                metadata={"name": name, "base_url": base_url.rstrip("/")},
            )
            await session.flush()
            return panel

    async def list_marzban_panels(self) -> list[MarzbanPanel]:
        async with session_scope() as session:
            return await list_marzban_panels(session)

    async def assign_panel(
        self,
        *,
        reseller_telegram_id: int,
        panel_id: str,
        marzban_admin_username: str | None = None,
    ) -> ResellerPanelAssignment:
        async with session_scope() as session:
            reseller = await get_reseller_by_telegram_id(
                session,
                telegram_id=reseller_telegram_id,
            )
            if reseller is None:
                raise ValueError("reseller_not_found")
            panel = await get_marzban_panel(session, panel_id=panel_id)
            if panel is None:
                raise ValueError("panel_not_found")
            assignment = await assign_panel_to_reseller(
                session,
                reseller_id=reseller.id,
                panel_id=panel.id,
                marzban_admin_username=marzban_admin_username,
            )
            await record_audit_log(
                session,
                action="reseller_panel.assign",
                actor_type=AuditActorType.SUPER_USER,
                reseller_id=reseller.id,
                target_type="reseller_panel_assignment",
                target_id=assignment.id,
                metadata={"panel_id": panel.id, "reseller_telegram_id": reseller_telegram_id},
            )
            await session.flush()
            return assignment

    async def start_seller_bot(self, *, seller_bot_id: str) -> SellerBot:
        if self.settings is None:
            raise RuntimeError("settings_required")
        runtime = self._runtime_controller()
        async with session_scope() as session:
            seller_bot = await get_seller_bot(session, seller_bot_id=seller_bot_id)
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            token = self.secret_box.decrypt(seller_bot.token_encrypted)
            if not token:
                await update_seller_runtime_state(
                    session,
                    seller_bot=seller_bot,
                    status=SellerBotStatus.ERROR,
                    last_error="seller token cannot be decrypted",
                )
                raise ValueError("seller_token_unavailable")
            env = self._seller_environment(seller_bot_id=seller_bot.id, token=token)
            try:
                container_id = runtime.start_seller(
                    seller_bot_id=seller_bot.id,
                    environment=env,
                    container_id=seller_bot.container_id,
                )
            except Exception as exc:
                await update_seller_runtime_state(
                    session,
                    seller_bot=seller_bot,
                    status=SellerBotStatus.ERROR,
                    last_error=str(exc),
                )
                raise
            await update_seller_runtime_state(
                session,
                seller_bot=seller_bot,
                status=SellerBotStatus.RUNNING,
                container_id=container_id,
                container_name=seller_container_name(seller_bot.id),
                last_error=None,
            )
            await record_audit_log(
                session,
                action="seller_bot.start",
                actor_type=AuditActorType.SUPER_USER,
                reseller_id=seller_bot.reseller_id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={"container_id": container_id},
            )
            await session.flush()
            return seller_bot

    async def stop_seller_bot(self, *, seller_bot_id: str) -> SellerBot:
        if self.settings is None:
            raise RuntimeError("settings_required")
        runtime = self._runtime_controller()
        async with session_scope() as session:
            seller_bot = await get_seller_bot(session, seller_bot_id=seller_bot_id)
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            runtime.stop_seller(container_id=seller_bot.container_id)
            await update_seller_runtime_state(
                session,
                seller_bot=seller_bot,
                status=SellerBotStatus.STOPPED,
                container_id=seller_bot.container_id,
                container_name=seller_bot.container_name,
                last_error=None,
            )
            await record_audit_log(
                session,
                action="seller_bot.stop",
                actor_type=AuditActorType.SUPER_USER,
                reseller_id=seller_bot.reseller_id,
                target_type="seller_bot",
                target_id=seller_bot.id,
            )
            await session.flush()
            return seller_bot

    async def seller_health(self, *, seller_bot_id: str) -> SellerRuntimeStatus:
        runtime = self._runtime_controller()
        async with session_scope() as session:
            seller_bot = await get_seller_bot(session, seller_bot_id=seller_bot_id)
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            health = runtime.seller_health(container_id=seller_bot.container_id)
            return SellerRuntimeStatus(seller_bot=seller_bot, health=health)

    async def seller_logs(self, *, seller_bot_id: str, tail: int = 120) -> SellerRuntimeStatus:
        runtime = self._runtime_controller()
        async with session_scope() as session:
            seller_bot = await get_seller_bot(session, seller_bot_id=seller_bot_id)
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            health = runtime.seller_health(container_id=seller_bot.container_id)
            logs = runtime.seller_logs(container_id=seller_bot.container_id, tail=tail)
            return SellerRuntimeStatus(seller_bot=seller_bot, health=health, logs=logs)

    async def create_global_plan(
        self,
        *,
        name: str,
        price: float,
        duration_days: int,
        data_limit_gb: int | None,
    ) -> Plan:
        async with session_scope() as session:
            plan = await create_plan(
                session,
                name=name,
                price=price,
                duration_days=duration_days,
                data_limit_gb=data_limit_gb,
            )
            await record_audit_log(
                session,
                action="plan.create_global",
                actor_type=AuditActorType.SUPER_USER,
                target_type="plan",
                target_id=plan.id,
                metadata={"name": name, "price": price},
            )
            await session.flush()
            return plan

    async def create_reseller_plan(
        self,
        *,
        reseller_telegram_id: int,
        name: str,
        price: float,
        duration_days: int,
        data_limit_gb: int | None,
    ) -> Plan:
        async with session_scope() as session:
            reseller = await get_reseller_by_telegram_id(
                session,
                telegram_id=reseller_telegram_id,
            )
            if reseller is None:
                raise ValueError("reseller_not_found")
            plan = await create_plan(
                session,
                reseller_id=reseller.id,
                name=name,
                price=price,
                duration_days=duration_days,
                data_limit_gb=data_limit_gb,
            )
            await session.flush()
            return plan

    async def list_plans(self) -> list[Plan]:
        async with session_scope() as session:
            return await list_all_plans(session)

    async def create_global_discount(
        self,
        *,
        code: str,
        discount_type: DiscountType,
        amount: float,
        max_uses: int | None = None,
    ) -> DiscountCode:
        async with session_scope() as session:
            discount = await create_discount_code(
                session,
                code=code,
                discount_type=discount_type,
                amount=amount,
                max_uses=max_uses,
            )
            await record_audit_log(
                session,
                action="discount.create_global",
                actor_type=AuditActorType.SUPER_USER,
                target_type="discount_code",
                target_id=discount.id,
                metadata={"code": code.upper(), "discount_type": discount_type.value},
            )
            await session.flush()
            return discount

    async def list_discounts(self) -> list[DiscountCode]:
        async with session_scope() as session:
            return await list_discount_codes(session)

    async def create_global_broadcast(
        self,
        *,
        admin_telegram_id: int,
        title: str,
        body: str,
    ) -> BroadcastDraft:
        async with session_scope() as session:
            broadcast, recipients = await create_global_broadcast(
                session,
                title=title,
                body=body,
                created_by_telegram_id=admin_telegram_id,
            )
            await record_audit_log(
                session,
                action="broadcast.create_global",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=admin_telegram_id,
                target_type="broadcast",
                target_id=broadcast.id,
                metadata={"target_count": len(recipients)},
            )
            await session.flush()
            return BroadcastDraft(broadcast=broadcast, recipients=recipients)

    async def get_global_broadcast_recipients(
        self,
        *,
        broadcast_id: str,
    ) -> BroadcastDraft:
        async with session_scope() as session:
            broadcast = await get_global_broadcast(session, broadcast_id=broadcast_id)
            if broadcast is None:
                raise ValueError("broadcast_not_found")
            recipients = await list_pending_broadcast_recipients(
                session,
                broadcast_id=broadcast.id,
            )
            return BroadcastDraft(broadcast=broadcast, recipients=recipients)

    async def mark_global_broadcast_sent(
        self,
        *,
        broadcast_id: str,
        delivered_telegram_ids: set[int],
    ) -> Broadcast:
        async with session_scope() as session:
            broadcast = await get_global_broadcast(session, broadcast_id=broadcast_id)
            if broadcast is None:
                raise ValueError("broadcast_not_found")
            recipients = await list_pending_broadcast_recipients(
                session,
                broadcast_id=broadcast.id,
            )
            delivered = [
                recipient
                for recipient in recipients
                if recipient.telegram_user_id in delivered_telegram_ids
            ]
            await mark_broadcast_sent(session, broadcast=broadcast, recipients=delivered)
            await session.flush()
            return broadcast

    async def global_report(self, *, days: int = 1) -> dict[str, float | int]:
        async with session_scope() as session:
            since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
            return await global_sales_report(session, since=since)

    async def set_forced_join_chats(self, *, chats: list[ForcedJoinChat]) -> list[ForcedJoinChat]:
        async with session_scope() as session:
            await set_global_setting(
                session,
                key=FORCED_JOIN_CHATS_KEY,
                value=encode_forced_join_chats(chats),
            )
            await session.flush()
            return chats

    async def get_forced_join_chats(self) -> list[ForcedJoinChat]:
        async with session_scope() as session:
            setting = await get_global_setting(session, key=FORCED_JOIN_CHATS_KEY)
            return decode_forced_join_chats(setting.value if setting else None)

    def _runtime_controller(self) -> SellerRuntimeController:
        if self.settings is None:
            raise RuntimeError("settings_required")
        if self.runtime_controller is not None:
            return self.runtime_controller
        return DockerSellerRuntimeController.from_settings(self.settings)

    def _seller_environment(self, *, seller_bot_id: str, token: str) -> dict[str, str]:
        if self.settings is None:
            raise RuntimeError("settings_required")
        env = {
            "APP_ROLE": "seller_bot",
            "SELLER_BOT_ID": seller_bot_id,
            "SELLER_BOT_TOKEN": token,
            "DATABASE_URL": self.settings.database_url,
            "FERNET_KEY": self.settings.fernet_key,
            "MARZBAN_TOKEN_PATH": self.settings.marzban_token_path,
            "API_TIMEOUT_SECONDS": str(self.settings.api_timeout_seconds),
        }
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"):
            value = os.getenv(key)
            if value:
                env[key] = value
        return env
