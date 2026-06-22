from __future__ import annotations

import os
from dataclasses import dataclass
import datetime as dt
from pathlib import Path
import subprocess

from aiogram.utils.token import TokenValidationError, validate_token

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
    create_external_bot_template,
    create_discount_code,
    create_global_broadcast,
    create_marzban_panel,
    create_plan,
    create_reseller,
    create_seller_bot,
    count_panel_assignments,
    get_marzban_panel,
    get_external_bot_template,
    get_external_bot_template_by_key,
    get_global_broadcast,
    get_global_setting,
    get_discount_code,
    get_panel_assignment,
    get_primary_panel_assignment,
    get_plan,
    get_seller_bot_quota_usage,
    global_sales_report,
    get_reseller_by_telegram_id,
    get_seller_bot,
    list_external_bot_templates,
    list_all_plans,
    list_active_panel_assignments,
    list_discount_codes,
    list_global_broadcasts,
    list_pending_broadcast_recipients,
    list_recent_audit_logs,
    list_seller_bots,
    mark_broadcast_sent,
    record_audit_log,
    set_marzban_panel_active,
    set_discount_code_active,
    set_global_setting,
    set_plan_active,
    list_marzban_panels,
    list_resellers,
    update_panel_assignment_routing,
    update_external_bot_template_sync_state,
    update_seller_bot_volume,
    update_seller_runtime_state,
    update_reseller_profile,
    upsert_telegram_user,
)
from vpn_bot_platform.common.models import (
    AuditActorType,
    MarzbanPanel,
    Reseller,
    ResellerStatus,
    ResellerPanelAssignment,
    SellerBot,
    SellerBotStatus,
    SellerBotUiProfile,
    Plan,
    PlanPurpose,
    DiscountCode,
    DiscountType,
    Broadcast,
    BroadcastRecipient,
    AuditLog,
    ExternalBotTemplate,
    SellerBotRuntimeType,
)
from vpn_bot_platform.integrations.docker_runtime import seller_container_name
from vpn_bot_platform.integrations.marzban import MarzbanClient, MarzbanCredentials
from vpn_bot_platform.integrations.runtime_controller import (
    DockerSellerRuntimeController,
    SellerRuntimeController,
)


@dataclass(frozen=True)
class RegisteredReseller:
    reseller: Reseller
    existed: bool


@dataclass(frozen=True)
class SellerBotProvisionResult:
    reseller: Reseller
    reseller_existed: bool
    panel: MarzbanPanel
    seller_bot: SellerBot
    assignment: ResellerPanelAssignment


@dataclass(frozen=True)
class SellerRuntimeStatus:
    seller_bot: SellerBot
    health: str
    logs: str | None = None


@dataclass(frozen=True)
class SellerBotQuota:
    limit_gb: int
    used_gb: int
    reserved_gb: int
    remaining_gb: int


@dataclass(frozen=True)
class SellerRuntimeSpec:
    environment: dict[str, str]
    command: list[str]


@dataclass(frozen=True)
class ExternalTemplateSyncResult:
    template: ExternalBotTemplate
    ok: bool
    message: str


@dataclass(frozen=True)
class BroadcastDraft:
    broadcast: Broadcast
    recipients: list[BroadcastRecipient]


@dataclass(frozen=True)
class ResellerPanelSummary:
    assignment: ResellerPanelAssignment
    panel: MarzbanPanel


@dataclass(frozen=True)
class PanelDetail:
    panel: MarzbanPanel
    assignment_count: int
    auth_type: str


@dataclass(frozen=True)
class PanelTestResult:
    panel: MarzbanPanel
    ok: bool
    message: str


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
        volume_limit_gb: int | None = 0,
        ui_profile: SellerBotUiProfile = SellerBotUiProfile.PLATFORM,
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
                volume_limit_gb=volume_limit_gb,
                ui_profile=ui_profile,
            )
            await record_audit_log(
                session,
                action="seller_bot.register",
                actor_type=AuditActorType.SUPER_USER,
                reseller_id=reseller.id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={
                    "reseller_telegram_id": reseller_telegram_id,
                    "bot_name": bot_name,
                    "volume_limit_gb": volume_limit_gb,
                    "ui_profile": ui_profile.value,
                },
            )
            await session.flush()
            return seller_bot

    async def register_seller_bot_with_panel(
        self,
        *,
        reseller_telegram_id: int,
        bot_name: str,
        bot_token: str,
        panel_id: str,
        marzban_admin_username: str | None = None,
        volume_limit_gb: int | None = 0,
        ui_profile: SellerBotUiProfile = SellerBotUiProfile.PLATFORM,
        actor_telegram_id: int | None = None,
    ) -> tuple[SellerBot, ResellerPanelAssignment]:
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
            seller_bot = await create_seller_bot(
                session,
                reseller_id=reseller.id,
                name=bot_name,
                token=bot_token,
                secret_box=self.secret_box,
                volume_limit_gb=volume_limit_gb,
                ui_profile=ui_profile,
            )
            assignment = await assign_panel_to_reseller(
                session,
                reseller_id=reseller.id,
                panel_id=panel.id,
                marzban_admin_username=marzban_admin_username,
            )
            await record_audit_log(
                session,
                action="seller_bot.register_with_panel",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=reseller.id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={
                    "reseller_telegram_id": reseller_telegram_id,
                    "bot_name": bot_name,
                    "panel_id": panel.id,
                    "marzban_admin_username": marzban_admin_username,
                    "volume_limit_gb": volume_limit_gb,
                    "ui_profile": ui_profile.value,
                },
            )
            await session.flush()
            return seller_bot, assignment

    async def provision_seller_bot_with_password_panel(
        self,
        *,
        reseller_telegram_id: int,
        reseller_display_name: str,
        bot_name: str,
        bot_token: str,
        panel_name: str,
        panel_base_url: str,
        panel_username: str,
        panel_password: str,
        marzban_admin_username: str | None = None,
        volume_limit_gb: int | None = 0,
        actor_telegram_id: int | None = None,
    ) -> SellerBotProvisionResult:
        if not panel_username or not panel_password:
            raise ValueError("panel_credentials_required")
        async with session_scope() as session:
            await upsert_telegram_user(
                session,
                telegram_id=reseller_telegram_id,
                first_name=reseller_display_name,
            )
            reseller = await get_reseller_by_telegram_id(
                session,
                telegram_id=reseller_telegram_id,
            )
            reseller_existed = reseller is not None
            if reseller is None:
                reseller = await create_reseller(
                    session,
                    telegram_user_id=reseller_telegram_id,
                    display_name=reseller_display_name,
                )
                await record_audit_log(
                    session,
                    action="reseller.create",
                    actor_type=AuditActorType.SUPER_USER,
                    actor_telegram_id=actor_telegram_id,
                    reseller_id=reseller.id,
                    target_type="reseller",
                    target_id=reseller.id,
                    metadata={
                        "telegram_user_id": reseller_telegram_id,
                        "display_name": reseller_display_name,
                    },
                )
                await session.flush()
            panel = await create_marzban_panel(
                session,
                name=panel_name,
                base_url=panel_base_url,
                username=panel_username,
                password=panel_password,
                secret_box=self.secret_box,
            )
            await session.flush()
            seller_bot = await create_seller_bot(
                session,
                reseller_id=reseller.id,
                name=bot_name,
                token=bot_token,
                secret_box=self.secret_box,
                volume_limit_gb=volume_limit_gb,
            )
            await session.flush()
            assignment = await assign_panel_to_reseller(
                session,
                reseller_id=reseller.id,
                panel_id=panel.id,
                marzban_admin_username=marzban_admin_username or panel_username,
            )
            await record_audit_log(
                session,
                action="seller_bot.provision_with_panel",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=reseller.id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={
                    "reseller_telegram_id": reseller_telegram_id,
                    "bot_name": bot_name,
                    "panel_id": panel.id,
                    "panel_name": panel_name,
                    "marzban_admin_username": assignment.marzban_admin_username,
                    "volume_limit_gb": volume_limit_gb,
                },
            )
            await session.flush()
            return SellerBotProvisionResult(
                reseller=reseller,
                reseller_existed=reseller_existed,
                panel=panel,
                seller_bot=seller_bot,
                assignment=assignment,
            )

    async def register_external_bot_template(
        self,
        *,
        key: str,
        name: str,
        repo_url: str,
        ref: str = "main",
        local_path: str | None = None,
        license_name: str | None = None,
        runtime_adapter: str = "manual",
        actor_telegram_id: int | None = None,
    ) -> ExternalBotTemplate:
        key = key.strip().lower()
        if not key or any(char.isspace() for char in key):
            raise ValueError("invalid_template_key")
        async with session_scope() as session:
            existing = await get_external_bot_template_by_key(session, key=key)
            if existing is not None:
                raise ValueError("external_template_exists")
            template = await create_external_bot_template(
                session,
                key=key,
                name=name.strip(),
                repo_url=repo_url.strip(),
                ref=(ref or "main").strip(),
                local_path=local_path.strip() if local_path else None,
                license_name=license_name.strip() if license_name else None,
                runtime_adapter=(runtime_adapter or "manual").strip(),
            )
            await record_audit_log(
                session,
                action="external_bot_template.register",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                target_type="external_bot_template",
                target_id=template.id,
                metadata={
                    "key": template.key,
                    "name": template.name,
                    "repo_url": template.repo_url,
                    "ref": template.ref,
                    "local_path": template.local_path,
                    "runtime_adapter": template.runtime_adapter,
                },
            )
            await session.flush()
            return template

    async def list_external_bot_templates(self) -> list[ExternalBotTemplate]:
        async with session_scope() as session:
            return await list_external_bot_templates(session)

    async def sync_external_bot_template(
        self,
        *,
        template_id_or_key: str,
        actor_telegram_id: int | None = None,
    ) -> ExternalTemplateSyncResult:
        async with session_scope() as session:
            template = await get_external_bot_template(session, template_id=template_id_or_key)
            if template is None:
                template = await get_external_bot_template_by_key(session, key=template_id_or_key)
            if template is None:
                raise ValueError("external_template_not_found")

            commit: str | None = None
            error: str | None = None
            if not template.local_path:
                error = "local_path_not_configured"
            else:
                path = Path(template.local_path)
                if not path.exists():
                    error = f"local_path_missing: {template.local_path}"
                else:
                    try:
                        result = subprocess.run(
                            ["git", "-C", str(path), "rev-parse", "HEAD"],
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        commit = result.stdout.strip()
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
                        if len(template.ref) >= 7:
                            commit = template.ref
                        else:
                            error = str(exc)

            await update_external_bot_template_sync_state(
                session,
                template=template,
                commit=commit,
                error=error,
            )
            await record_audit_log(
                session,
                action="external_bot_template.sync",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                target_type="external_bot_template",
                target_id=template.id,
                metadata={"key": template.key, "commit": commit, "error": error},
            )
            await session.flush()
            return ExternalTemplateSyncResult(
                template=template,
                ok=error is None,
                message=commit or error or "synced",
            )

    async def register_external_seller_bot(
        self,
        *,
        reseller_telegram_id: int,
        bot_name: str,
        bot_token: str,
        template_id_or_key: str,
        volume_limit_gb: int | None = 0,
        actor_telegram_id: int | None = None,
    ) -> SellerBot:
        async with session_scope() as session:
            reseller = await get_reseller_by_telegram_id(
                session,
                telegram_id=reseller_telegram_id,
            )
            if reseller is None:
                raise ValueError("reseller_not_found")
            template = await get_external_bot_template(session, template_id=template_id_or_key)
            if template is None:
                template = await get_external_bot_template_by_key(session, key=template_id_or_key)
            if template is None or not template.is_active:
                raise ValueError("external_template_not_found")
            seller_bot = await create_seller_bot(
                session,
                reseller_id=reseller.id,
                name=bot_name,
                token=bot_token,
                secret_box=self.secret_box,
                runtime_type=SellerBotRuntimeType.EXTERNAL_TEMPLATE,
                external_template_id=template.id,
                volume_limit_gb=volume_limit_gb,
            )
            await record_audit_log(
                session,
                action="seller_bot.register_external",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=reseller.id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={
                    "reseller_telegram_id": reseller_telegram_id,
                    "bot_name": bot_name,
                    "external_template_key": template.key,
                    "volume_limit_gb": volume_limit_gb,
                },
            )
            await session.flush()
            return seller_bot

    async def register_external_seller_bot_with_panel(
        self,
        *,
        reseller_telegram_id: int,
        bot_name: str,
        bot_token: str,
        template_id_or_key: str,
        panel_id: str,
        marzban_admin_username: str | None = None,
        volume_limit_gb: int | None = 0,
        actor_telegram_id: int | None = None,
    ) -> tuple[SellerBot, ResellerPanelAssignment]:
        async with session_scope() as session:
            reseller = await get_reseller_by_telegram_id(
                session,
                telegram_id=reseller_telegram_id,
            )
            if reseller is None:
                raise ValueError("reseller_not_found")
            template = await get_external_bot_template(session, template_id=template_id_or_key)
            if template is None:
                template = await get_external_bot_template_by_key(session, key=template_id_or_key)
            if template is None or not template.is_active:
                raise ValueError("external_template_not_found")
            panel = await get_marzban_panel(session, panel_id=panel_id)
            if panel is None:
                raise ValueError("panel_not_found")
            seller_bot = await create_seller_bot(
                session,
                reseller_id=reseller.id,
                name=bot_name,
                token=bot_token,
                secret_box=self.secret_box,
                runtime_type=SellerBotRuntimeType.EXTERNAL_TEMPLATE,
                external_template_id=template.id,
                volume_limit_gb=volume_limit_gb,
            )
            assignment = await assign_panel_to_reseller(
                session,
                reseller_id=reseller.id,
                panel_id=panel.id,
                marzban_admin_username=marzban_admin_username,
            )
            await record_audit_log(
                session,
                action="seller_bot.register_external_with_panel",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=reseller.id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={
                    "reseller_telegram_id": reseller_telegram_id,
                    "bot_name": bot_name,
                    "external_template_key": template.key,
                    "panel_id": panel.id,
                    "marzban_admin_username": marzban_admin_username,
                    "volume_limit_gb": volume_limit_gb,
                },
            )
            await session.flush()
            return seller_bot, assignment

    async def list_resellers(self) -> list[Reseller]:
        async with session_scope() as session:
            return await list_resellers(session)

    async def list_seller_bots(self) -> list[SellerBot]:
        async with session_scope() as session:
            return await list_seller_bots(session)

    async def set_seller_bot_volume(
        self,
        *,
        seller_bot_id: str,
        volume_limit_gb: int | None,
        actor_telegram_id: int | None = None,
    ) -> SellerBot:
        async with session_scope() as session:
            seller_bot = await get_seller_bot(session, seller_bot_id=seller_bot_id)
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            await update_seller_bot_volume(
                session,
                seller_bot=seller_bot,
                volume_limit_gb=volume_limit_gb or 0,
            )
            await record_audit_log(
                session,
                action="seller_bot.volume_update",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={"volume_limit_gb": volume_limit_gb or 0},
            )
            await session.flush()
            return seller_bot

    async def add_seller_bot_volume(
        self,
        *,
        seller_bot_id: str,
        added_gb: int,
        actor_telegram_id: int | None = None,
    ) -> SellerBotQuota:
        if added_gb <= 0:
            raise ValueError("invalid_volume")
        async with session_scope() as session:
            seller_bot = await get_seller_bot(session, seller_bot_id=seller_bot_id)
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            before = await get_seller_bot_quota_usage(session, seller_bot_id=seller_bot.id)
            old_limit_gb = before.limit_gb or 0
            new_limit_gb = old_limit_gb + added_gb
            await update_seller_bot_volume(
                session,
                seller_bot=seller_bot,
                volume_limit_gb=new_limit_gb,
            )
            after = await get_seller_bot_quota_usage(session, seller_bot_id=seller_bot.id)
            await record_audit_log(
                session,
                action="seller_bot.volume_add",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={
                    "old_limit_gb": old_limit_gb,
                    "added_gb": added_gb,
                    "new_limit_gb": new_limit_gb,
                    "used_gb": after.used_gb,
                    "reserved_gb": after.reserved_gb,
                    "remaining_gb": after.remaining_gb,
                },
            )
            await session.flush()
            return SellerBotQuota(
                limit_gb=after.limit_gb or 0,
                used_gb=after.used_gb,
                reserved_gb=after.reserved_gb,
                remaining_gb=after.remaining_gb or 0,
            )

    async def seller_bot_quota(self, *, seller_bot_id: str) -> SellerBotQuota:
        async with session_scope() as session:
            usage = await get_seller_bot_quota_usage(session, seller_bot_id=seller_bot_id)
            return SellerBotQuota(
                limit_gb=usage.limit_gb or 0,
                used_gb=usage.used_gb,
                reserved_gb=usage.reserved_gb,
                remaining_gb=usage.remaining_gb or 0,
            )
    async def rename_reseller(
        self,
        *,
        reseller_telegram_id: int,
        display_name: str,
        actor_telegram_id: int | None = None,
    ) -> Reseller:
        async with session_scope() as session:
            reseller = await get_reseller_by_telegram_id(
                session,
                telegram_id=reseller_telegram_id,
            )
            if reseller is None:
                raise ValueError("reseller_not_found")
            await update_reseller_profile(session, reseller=reseller, display_name=display_name)
            await record_audit_log(
                session,
                action="reseller.rename",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=reseller.id,
                target_type="reseller",
                target_id=reseller.id,
                metadata={"telegram_user_id": reseller_telegram_id, "display_name": display_name},
            )
            await session.flush()
            return reseller

    async def set_reseller_status(
        self,
        *,
        reseller_telegram_id: int,
        status: ResellerStatus,
        actor_telegram_id: int | None = None,
    ) -> Reseller:
        async with session_scope() as session:
            reseller = await get_reseller_by_telegram_id(
                session,
                telegram_id=reseller_telegram_id,
            )
            if reseller is None:
                raise ValueError("reseller_not_found")
            await update_reseller_profile(session, reseller=reseller, status=status.value)
            await record_audit_log(
                session,
                action="reseller.status_update",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=reseller.id,
                target_type="reseller",
                target_id=reseller.id,
                metadata={"telegram_user_id": reseller_telegram_id, "status": status.value},
            )
            await session.flush()
            return reseller

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

    async def list_panel_assignments_for_reseller(self, *, reseller_id: str) -> list[ResellerPanelSummary]:
        async with session_scope() as session:
            rows = await list_active_panel_assignments(session, reseller_id=reseller_id)
            return [
                ResellerPanelSummary(assignment=assignment, panel=panel)
                for assignment, panel in rows
            ]

    async def get_panel_detail(self, *, panel_id: str) -> PanelDetail:
        async with session_scope() as session:
            panel = await get_marzban_panel(session, panel_id=panel_id)
            if panel is None:
                raise ValueError("panel_not_found")
            assignment_count = await count_panel_assignments(session, panel_id=panel.id)
            auth_type = "token" if panel.token_encrypted else "password"
            return PanelDetail(panel=panel, assignment_count=assignment_count, auth_type=auth_type)

    async def disable_panel(
        self,
        *,
        panel_id: str,
        actor_telegram_id: int | None = None,
    ) -> PanelDetail:
        async with session_scope() as session:
            panel = await get_marzban_panel(session, panel_id=panel_id)
            if panel is None:
                raise ValueError("panel_not_found")
            await set_marzban_panel_active(session, panel=panel, is_active=False)
            await record_audit_log(
                session,
                action="marzban_panel.disable",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                target_type="marzban_panel",
                target_id=panel.id,
                metadata={"name": panel.name, "base_url": panel.base_url},
            )
            assignment_count = await count_panel_assignments(session, panel_id=panel.id)
            await session.flush()
            auth_type = "token" if panel.token_encrypted else "password"
            return PanelDetail(panel=panel, assignment_count=assignment_count, auth_type=auth_type)

    async def test_panel_connection(self, *, panel_id: str) -> PanelTestResult:
        async with session_scope() as session:
            panel = await get_marzban_panel(session, panel_id=panel_id)
            if panel is None:
                raise ValueError("panel_not_found")
            token = self.secret_box.decrypt(panel.token_encrypted)
            username = self.secret_box.decrypt(panel.username_encrypted)
            password = self.secret_box.decrypt(panel.password_encrypted)
            auth_method = "token" if token else "password"
            client = MarzbanClient(
                MarzbanCredentials(
                    base_url=panel.base_url,
                    auth_method=auth_method,
                    token=token,
                    username=username,
                    password=password,
                    token_path=self.settings.marzban_token_path if self.settings else "/api/admin/token",
                )
            )
            try:
                current_admin = await client.get_current_admin()
            except Exception as exc:
                return PanelTestResult(panel=panel, ok=False, message=str(exc)[:300])
            username_value = current_admin.get("username") if isinstance(current_admin, dict) else None
            message = f"Connected as {username_value}" if username_value else "Connection succeeded."
            return PanelTestResult(panel=panel, ok=True, message=message)

    async def assign_panel(
        self,
        *,
        reseller_telegram_id: int,
        panel_id: str,
        marzban_admin_username: str | None = None,
        priority: int = 100,
        weight: int = 1,
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
                priority=priority,
                weight=weight,
            )
            await record_audit_log(
                session,
                action="reseller_panel.assign",
                actor_type=AuditActorType.SUPER_USER,
                reseller_id=reseller.id,
                target_type="reseller_panel_assignment",
                target_id=assignment.id,
                metadata={
                    "panel_id": panel.id,
                    "reseller_telegram_id": reseller_telegram_id,
                    "priority": priority,
                    "weight": weight,
                },
            )
            await session.flush()
            return assignment

    async def update_panel_assignment_routing(
        self,
        *,
        assignment_id: str,
        priority: int,
        weight: int,
        actor_telegram_id: int | None = None,
    ) -> ResellerPanelAssignment:
        async with session_scope() as session:
            assignment = await get_panel_assignment(session, assignment_id=assignment_id)
            if assignment is None:
                raise ValueError("assignment_not_found")
            await update_panel_assignment_routing(
                session,
                assignment=assignment,
                priority=priority,
                weight=weight,
            )
            await record_audit_log(
                session,
                action="reseller_panel.routing_update",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=assignment.reseller_id,
                target_type="reseller_panel_assignment",
                target_id=assignment.id,
                metadata={"priority": priority, "weight": weight, "panel_id": assignment.panel_id},
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
            if seller_bot.runtime_type != SellerBotRuntimeType.NATIVE.value:
                raise RuntimeError("external_runtime_adapter_not_implemented")
            token = self.secret_box.decrypt(seller_bot.token_encrypted)
            if not token:
                await update_seller_runtime_state(
                    session,
                    seller_bot=seller_bot,
                    status=SellerBotStatus.ERROR,
                    last_error="seller token cannot be decrypted",
                )
                raise ValueError("seller_token_unavailable")
            try:
                validate_token(token)
            except TokenValidationError as exc:
                await update_seller_runtime_state(
                    session,
                    seller_bot=seller_bot,
                    status=SellerBotStatus.ERROR,
                    container_id=None,
                    container_name=None,
                    last_error=f"invalid seller token: {exc}",
                )
                raise ValueError("seller_token_invalid") from exc
            spec = await self._seller_runtime_spec(session, seller_bot=seller_bot, token=token)
            try:
                container_id = runtime.start_seller(
                    seller_bot_id=seller_bot.id,
                    environment=spec.environment,
                    container_id=seller_bot.container_id,
                    command=spec.command,
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

    async def restart_seller_bot(self, *, seller_bot_id: str) -> SellerBot:
        if self.settings is None:
            raise RuntimeError("settings_required")
        runtime = self._runtime_controller()
        async with session_scope() as session:
            seller_bot = await get_seller_bot(session, seller_bot_id=seller_bot_id)
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            if seller_bot.runtime_type != SellerBotRuntimeType.NATIVE.value:
                raise RuntimeError("external_runtime_adapter_not_implemented")
            token = self.secret_box.decrypt(seller_bot.token_encrypted)
            if not token:
                await update_seller_runtime_state(
                    session,
                    seller_bot=seller_bot,
                    status=SellerBotStatus.ERROR,
                    last_error="seller token cannot be decrypted",
                )
                raise ValueError("seller_token_unavailable")
            try:
                validate_token(token)
            except TokenValidationError as exc:
                await update_seller_runtime_state(
                    session,
                    seller_bot=seller_bot,
                    status=SellerBotStatus.ERROR,
                    container_id=None,
                    container_name=None,
                    last_error=f"invalid seller token: {exc}",
                )
                raise ValueError("seller_token_invalid") from exc
            spec = await self._seller_runtime_spec(session, seller_bot=seller_bot, token=token)
            try:
                container_id = runtime.start_seller(
                    seller_bot_id=seller_bot.id,
                    environment=spec.environment,
                    container_id=seller_bot.container_id,
                    command=spec.command,
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
                action="seller_bot.restart",
                actor_type=AuditActorType.SUPER_USER,
                reseller_id=seller_bot.reseller_id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={"container_id": container_id},
            )
            await session.flush()
            return seller_bot

    async def disable_seller_bot(self, *, seller_bot_id: str) -> SellerBot:
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
                status=SellerBotStatus.DISABLED,
                container_id=None,
                container_name=None,
                last_error="disabled by super user",
            )
            await record_audit_log(
                session,
                action="seller_bot.disable",
                actor_type=AuditActorType.SUPER_USER,
                reseller_id=seller_bot.reseller_id,
                target_type="seller_bot",
                target_id=seller_bot.id,
            )
            await session.flush()
            return seller_bot

    async def delete_seller_bot(
        self,
        *,
        seller_bot_id: str,
        actor_telegram_id: int | None = None,
    ) -> SellerBot:
        runtime_error: str | None = None
        runtime = self.runtime_controller
        if runtime is None and self.settings is not None:
            runtime = DockerSellerRuntimeController.from_settings(self.settings)
        async with session_scope() as session:
            seller_bot = await get_seller_bot(session, seller_bot_id=seller_bot_id)
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            if runtime is not None:
                try:
                    runtime.stop_seller(container_id=seller_bot.container_id)
                except Exception as exc:
                    runtime_error = str(exc)[:300]
            await update_seller_runtime_state(
                session,
                seller_bot=seller_bot,
                status=SellerBotStatus.DISABLED,
                container_id=None,
                container_name=None,
                last_error=runtime_error or "deleted by super user",
            )
            await record_audit_log(
                session,
                action="seller_bot.delete",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="seller_bot",
                target_id=seller_bot.id,
                metadata={"runtime_stop_error": runtime_error},
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
        purpose: PlanPurpose = PlanPurpose.PURCHASE,
    ) -> Plan:
        async with session_scope() as session:
            plan = await create_plan(
                session,
                name=name,
                price=price,
                duration_days=duration_days,
                data_limit_gb=data_limit_gb,
                purpose=purpose,
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
        purpose: PlanPurpose = PlanPurpose.PURCHASE,
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
                purpose=purpose,
            )
            await session.flush()
            return plan

    async def list_plans(self) -> list[Plan]:
        async with session_scope() as session:
            return await list_all_plans(session)

    async def get_plan(self, *, plan_id: str) -> Plan:
        async with session_scope() as session:
            plan = await get_plan(session, plan_id=plan_id)
            if plan is None:
                raise ValueError("plan_not_found")
            return plan

    async def set_plan_status(
        self,
        *,
        plan_id: str,
        is_active: bool,
        actor_telegram_id: int | None = None,
    ) -> Plan:
        async with session_scope() as session:
            plan = await get_plan(session, plan_id=plan_id)
            if plan is None:
                raise ValueError("plan_not_found")
            await set_plan_active(session, plan=plan, is_active=is_active)
            await record_audit_log(
                session,
                action="plan.enable" if is_active else "plan.disable",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=plan.reseller_id,
                target_type="plan",
                target_id=plan.id,
                metadata={"name": plan.name, "is_active": is_active},
            )
            await session.flush()
            return plan

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

    async def get_discount(self, *, discount_id: str) -> DiscountCode:
        async with session_scope() as session:
            discount = await get_discount_code(session, discount_id=discount_id)
            if discount is None:
                raise ValueError("discount_not_found")
            return discount

    async def set_discount_status(
        self,
        *,
        discount_id: str,
        is_active: bool,
        actor_telegram_id: int | None = None,
    ) -> DiscountCode:
        async with session_scope() as session:
            discount = await get_discount_code(session, discount_id=discount_id)
            if discount is None:
                raise ValueError("discount_not_found")
            await set_discount_code_active(session, discount=discount, is_active=is_active)
            await record_audit_log(
                session,
                action="discount.enable" if is_active else "discount.disable",
                actor_type=AuditActorType.SUPER_USER,
                actor_telegram_id=actor_telegram_id,
                reseller_id=discount.reseller_id,
                target_type="discount_code",
                target_id=discount.id,
                metadata={"code": discount.code, "is_active": is_active},
            )
            await session.flush()
            return discount

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

    async def get_global_broadcast(self, *, broadcast_id: str) -> Broadcast:
        async with session_scope() as session:
            broadcast = await get_global_broadcast(session, broadcast_id=broadcast_id)
            if broadcast is None:
                raise ValueError("broadcast_not_found")
            return broadcast

    async def list_global_broadcasts(self, *, limit: int = 10) -> list[Broadcast]:
        async with session_scope() as session:
            return await list_global_broadcasts(session, limit=limit)

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

    async def recent_audit_logs(self, *, limit: int = 10) -> list[AuditLog]:
        async with session_scope() as session:
            return await list_recent_audit_logs(session, limit=limit)

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

    async def _seller_runtime_spec(self, session, *, seller_bot: SellerBot, token: str) -> SellerRuntimeSpec:
        if seller_bot.ui_profile == SellerBotUiProfile.SIMPLE_SELLER.value:
            return await self._simple_seller_runtime_spec(session, seller_bot=seller_bot, token=token)
        return SellerRuntimeSpec(
            environment=self._platform_seller_environment(seller_bot_id=seller_bot.id, token=token),
            command=["python", "-m", "vpn_bot_platform.seller_bot.main"],
        )

    async def _simple_seller_runtime_spec(self, session, *, seller_bot: SellerBot, token: str) -> SellerRuntimeSpec:
        if self.settings is None:
            raise RuntimeError("settings_required")
        primary_assignment = await get_primary_panel_assignment(session, reseller_id=seller_bot.reseller_id)
        if primary_assignment is None:
            raise ValueError("seller_panel_assignment_not_found")
        assignment, panel = primary_assignment
        reseller = await session.get(Reseller, seller_bot.reseller_id)
        if reseller is None:
            raise ValueError("reseller_not_found")
        env = {
            "APP_ROLE": "simple_seller_bot",
            "SELLER_BOT_ID": seller_bot.id,
            "BOT_TOKEN": token,
            "DATABASE_PATH": f"/app/data/sellers/{seller_bot.id}/bot.sqlite3",
            "SELLER_DATABASE_PATH": f"/app/data/sellers/{seller_bot.id}/bot.sqlite3",
            "ADMIN_IDS": str(reseller.telegram_user_id),
            "MARZBAN_BASE_URL": panel.base_url,
            "MARZBAN_USERNAME": self.secret_box.decrypt(panel.username_encrypted) or "",
            "MARZBAN_PASSWORD": self.secret_box.decrypt(panel.password_encrypted) or "",
            "MARZBAN_TOKEN": self.secret_box.decrypt(panel.token_encrypted) or "",
            "MARZBAN_DEFAULT_PROXIES_JSON": self.settings.marzban_default_proxies_json,
            "API_TIMEOUT_SECONDS": str(self.settings.api_timeout_seconds),
        }
        if assignment.marzban_admin_username:
            env["MARZBAN_ADMIN_USERNAME"] = assignment.marzban_admin_username
        self._copy_proxy_env(env)
        return SellerRuntimeSpec(environment=env, command=["python", "-m", "bot"])

    def _platform_seller_environment(self, *, seller_bot_id: str, token: str) -> dict[str, str]:
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
        self._copy_proxy_env(env)
        return env

    @staticmethod
    def _copy_proxy_env(env: dict[str, str]) -> None:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"):
            value = os.getenv(key)
            if value:
                env[key] = value
