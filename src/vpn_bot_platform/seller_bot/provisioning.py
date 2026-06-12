from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from vpn_bot_platform.common.config import Settings
from vpn_bot_platform.common.crypto import SecretBox
from vpn_bot_platform.common.db import session_scope
from vpn_bot_platform.common.models import Order, Plan, SellerBot, VpnService
from vpn_bot_platform.common.repositories import (
    create_trial_grant,
    create_vpn_service,
    get_extra_volume_order_context,
    get_provisioning_order_context,
    get_renewal_order_context,
    get_seller_bot_with_reseller,
    get_trial_grant,
    get_marzban_panel,
    mark_order_completed,
    mark_order_failed,
    record_audit_log,
    upsert_buyer,
)
from vpn_bot_platform.common.models import AuditActorType
from vpn_bot_platform.integrations.marzban import (
    MarzbanClient,
    MarzbanCredentials,
    MarzbanUserCreate,
    MarzbanUserUpdate,
    gb_to_bytes,
    seconds_from_now,
)
from vpn_bot_platform.seller_bot.panel_routing import PanelRouter


class MarzbanCreateUserClient(Protocol):
    async def create_user(self, user: MarzbanUserCreate) -> dict:
        pass

    async def update_user(self, username: str, update: MarzbanUserUpdate) -> dict:
        pass


MarzbanClientFactory = Callable[[MarzbanCredentials], MarzbanCreateUserClient]


@dataclass(frozen=True)
class ProvisionedService:
    order: Order
    vpn_service: VpnService


class ProvisioningService:
    def __init__(
        self,
        *,
        seller_bot_id: str,
        settings: Settings,
        secret_box: SecretBox,
        marzban_client_factory: MarzbanClientFactory | None = None,
        panel_router: PanelRouter | None = None,
    ) -> None:
        self.seller_bot_id = seller_bot_id
        self.settings = settings
        self.secret_box = secret_box
        self.marzban_client_factory = marzban_client_factory or MarzbanClient
        self.panel_router = panel_router or PanelRouter()

    async def provision_order(self, *, admin_telegram_id: int, order_id: str) -> ProvisionedService:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            if seller_bot.reseller.telegram_user_id != admin_telegram_id:
                raise PermissionError("not_reseller_admin")

            context = await get_provisioning_order_context(
                session,
                reseller_id=seller_bot.reseller_id,
                order_id=order_id,
            )
            if context is None:
                raise ValueError("order_not_ready")
            order, buyer, plan = context

            routed_panel = await self.panel_router.choose_panel(
                session,
                reseller_id=seller_bot.reseller_id,
            )
            if routed_panel is None:
                await mark_order_failed(session, order=order)
                raise ValueError("panel_assignment_not_found")
            assignment, panel = routed_panel.assignment, routed_panel.panel

            credentials = self._panel_credentials(panel)
            marzban_user = self._build_marzban_user(
                seller_bot=seller_bot,
                plan=plan,
                buyer_telegram_id=buyer.telegram_user_id,
                owner_username=assignment.marzban_admin_username,
            )
            try:
                response = await self.marzban_client_factory(credentials).create_user(marzban_user)
            except Exception:
                await mark_order_failed(session, order=order)
                raise

            vpn_service = await create_vpn_service(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
                panel_id=panel.id,
                marzban_username=marzban_user.username,
                subscription_url=_extract_subscription_url(response),
                data_limit_gb=plan.data_limit_gb,
                expire_at=dt.datetime.fromtimestamp(marzban_user.expire or 0, dt.UTC)
                if marzban_user.expire
                else None,
            )
            await mark_order_completed(session, order=order)
            await record_audit_log(
                session,
                action="vpn_service.provision",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="vpn_service",
                target_id=vpn_service.id,
                metadata={"order_id": order.id, "panel_id": panel.id},
            )
            await session.flush()
            return ProvisionedService(order=order, vpn_service=vpn_service)

    async def apply_renewal(self, *, admin_telegram_id: int, order_id: str) -> ProvisionedService:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            if seller_bot.reseller.telegram_user_id != admin_telegram_id:
                raise PermissionError("not_reseller_admin")
            context = await get_renewal_order_context(
                session,
                reseller_id=seller_bot.reseller_id,
                order_id=order_id,
            )
            if context is None:
                raise ValueError("renewal_not_ready")
            order, vpn_service, plan = context
            panel = await get_marzban_panel(session, panel_id=vpn_service.panel_id)
            if panel is None or not panel.is_active:
                await mark_order_failed(session, order=order)
                raise ValueError("panel_not_found")

            new_expire = _renewed_expire_timestamp(vpn_service.expire_at, plan.duration_days)
            update = MarzbanUserUpdate(
                expire=new_expire,
                data_limit=gb_to_bytes(plan.data_limit_gb) if plan.data_limit_gb is not None else None,
                status="active",
            )
            try:
                await self.marzban_client_factory(self._panel_credentials(panel)).update_user(
                    vpn_service.marzban_username,
                    update,
                )
            except Exception:
                await mark_order_failed(session, order=order)
                raise

            vpn_service.expire_at = dt.datetime.fromtimestamp(new_expire, dt.UTC)
            vpn_service.data_limit_gb = plan.data_limit_gb
            vpn_service.is_active = True
            await mark_order_completed(session, order=order)
            await record_audit_log(
                session,
                action="vpn_service.renew",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="vpn_service",
                target_id=vpn_service.id,
                metadata={"order_id": order.id, "panel_id": panel.id},
            )
            await session.flush()
            return ProvisionedService(order=order, vpn_service=vpn_service)

    async def apply_extra_volume(self, *, admin_telegram_id: int, order_id: str) -> ProvisionedService:
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            if seller_bot.reseller.telegram_user_id != admin_telegram_id:
                raise PermissionError("not_reseller_admin")
            context = await get_extra_volume_order_context(
                session,
                reseller_id=seller_bot.reseller_id,
                order_id=order_id,
            )
            if context is None:
                raise ValueError("extra_volume_not_ready")
            order, vpn_service, plan = context
            panel = await get_marzban_panel(session, panel_id=vpn_service.panel_id)
            if panel is None or not panel.is_active:
                await mark_order_failed(session, order=order)
                raise ValueError("panel_not_found")

            new_data_limit_gb = _increased_data_limit(vpn_service.data_limit_gb, plan.data_limit_gb)
            update = MarzbanUserUpdate(
                data_limit=gb_to_bytes(new_data_limit_gb) if new_data_limit_gb is not None else None,
                status="active",
            )
            try:
                await self.marzban_client_factory(self._panel_credentials(panel)).update_user(
                    vpn_service.marzban_username,
                    update,
                )
            except Exception:
                await mark_order_failed(session, order=order)
                raise

            vpn_service.data_limit_gb = new_data_limit_gb
            vpn_service.is_active = True
            await mark_order_completed(session, order=order)
            await record_audit_log(
                session,
                action="vpn_service.extra_volume",
                actor_type=AuditActorType.RESELLER_ADMIN,
                actor_telegram_id=admin_telegram_id,
                reseller_id=seller_bot.reseller_id,
                target_type="vpn_service",
                target_id=vpn_service.id,
                metadata={
                    "order_id": order.id,
                    "panel_id": panel.id,
                    "added_gb": plan.data_limit_gb,
                    "new_data_limit_gb": new_data_limit_gb,
                },
            )
            await session.flush()
            return ProvisionedService(order=order, vpn_service=vpn_service)

    async def provision_trial(
        self,
        *,
        buyer_telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> VpnService:
        if not self.settings.trial_enabled:
            raise ValueError("trial_disabled")
        async with session_scope() as session:
            seller_bot = await get_seller_bot_with_reseller(
                session,
                seller_bot_id=self.seller_bot_id,
            )
            if seller_bot is None:
                raise ValueError("seller_bot_not_found")
            buyer = await upsert_buyer(
                session,
                reseller_id=seller_bot.reseller_id,
                telegram_id=buyer_telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
            )
            existing = await get_trial_grant(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
            )
            if existing is not None:
                raise ValueError("trial_already_used")
            routed_panel = await self.panel_router.choose_panel(
                session,
                reseller_id=seller_bot.reseller_id,
            )
            if routed_panel is None:
                raise ValueError("panel_assignment_not_found")
            assignment, panel = routed_panel.assignment, routed_panel.panel
            expire = seconds_from_now(self.settings.trial_duration_days)
            trial_user = MarzbanUserCreate(
                username=(
                    f"trial_r{seller_bot.reseller_id[:8]}_b{buyer_telegram_id}_"
                    f"{dt.datetime.now(dt.UTC):%Y%m%d%H%M%S}"
                ),
                proxies=json.loads(self.settings.marzban_default_proxies_json),
                expire=expire,
                data_limit=gb_to_bytes(self.settings.trial_data_limit_gb),
                note=(
                    f"trial=true; seller_bot={seller_bot.id}; buyer_tg={buyer_telegram_id}; "
                    f"owner={assignment.marzban_admin_username or '-'}"
                ),
            )
            response = await self.marzban_client_factory(
                self._panel_credentials(panel)
            ).create_user(trial_user)
            service = await create_vpn_service(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
                panel_id=panel.id,
                marzban_username=trial_user.username,
                subscription_url=_extract_subscription_url(response),
                data_limit_gb=self.settings.trial_data_limit_gb,
                expire_at=dt.datetime.fromtimestamp(expire, dt.UTC),
            )
            await session.flush()
            grant = await create_trial_grant(
                session,
                reseller_id=seller_bot.reseller_id,
                buyer_id=buyer.id,
                vpn_service_id=service.id,
            )
            grant.vpn_service_id = service.id
            await session.flush()
            return service

    def _panel_credentials(self, panel) -> MarzbanCredentials:
        token = self.secret_box.decrypt(panel.token_encrypted)
        username = self.secret_box.decrypt(panel.username_encrypted)
        password = self.secret_box.decrypt(panel.password_encrypted)
        auth_method = "token" if token else "password"
        return MarzbanCredentials(
            base_url=panel.base_url,
            auth_method=auth_method,
            token=token,
            username=username,
            password=password,
            token_path=self.settings.marzban_token_path,
            timeout_seconds=self.settings.api_timeout_seconds,
        )

    def _build_marzban_user(
        self,
        *,
        seller_bot: SellerBot,
        plan: Plan,
        buyer_telegram_id: int,
        owner_username: str | None,
    ) -> MarzbanUserCreate:
        unique_suffix = uuid.uuid4().hex[:8]
        username = (
            f"r{seller_bot.reseller_id[:8]}_b{buyer_telegram_id}_"
            f"{dt.datetime.now(dt.UTC):%Y%m%d%H%M%S}_{unique_suffix}"
        )
        note_parts = [f"seller_bot={seller_bot.id}", f"buyer_tg={buyer_telegram_id}"]
        if owner_username:
            note_parts.append(f"owner={owner_username}")
        return MarzbanUserCreate(
            username=username,
            proxies=json.loads(self.settings.marzban_default_proxies_json),
            expire=seconds_from_now(plan.duration_days),
            data_limit=gb_to_bytes(plan.data_limit_gb) if plan.data_limit_gb is not None else None,
            note="; ".join(note_parts),
        )


def _extract_subscription_url(response: dict) -> str | None:
    for key in ("subscription_url", "sub_url", "subscription"):
        value = response.get(key)
        if isinstance(value, str) and value:
            return value
    links = response.get("links")
    if isinstance(links, list) and links:
        first = links[0]
        return first if isinstance(first, str) else None
    return None


def _renewed_expire_timestamp(current_expire: dt.datetime | None, duration_days: int) -> int:
    now = dt.datetime.now(dt.UTC)
    if current_expire is not None and current_expire.tzinfo is None:
        current_expire = current_expire.replace(tzinfo=dt.UTC)
    base = current_expire if current_expire and current_expire > now else now
    return int((base + dt.timedelta(days=duration_days)).timestamp())


def _increased_data_limit(current_limit_gb: int | None, add_limit_gb: int | None) -> int | None:
    if current_limit_gb is None or add_limit_gb is None:
        return None
    return current_limit_gb + add_limit_gb
