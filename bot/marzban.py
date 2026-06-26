from __future__ import annotations

import json
import re
import secrets
import string
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from bot.db import PurchaseOffer, User


class MarzbanError(RuntimeError):
    pass


@dataclass(slots=True)
class MarzbanSubscription:
    username: str
    subscription_url: str
    expires_at: str


class MarzbanClient:
    def __init__(self, base_url: str, username: str = "", password: str = "", token: str = "", default_proxies_json: str = ""):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = token
        self.default_proxies_json = default_proxies_json or '{"vless":{},"vmess":{},"trojan":{}}'

    async def _retry_request(
        self,
        send: Callable[[], Awaitable[httpx.Response]],
        *,
        attempts: int = 3,
        delay_seconds: float = 0.5,
    ) -> httpx.Response:
        last_error: httpx.RequestError | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await send()
            except httpx.RequestError as exc:
                last_error = exc
                if attempt == attempts:
                    raise
                await asyncio.sleep(delay_seconds * attempt)
        if last_error:
            raise last_error
        raise MarzbanError("Unexpected Marzban retry state")

    async def create_subscription(self, offer: PurchaseOffer, buyer: User, requested_username: str | None = None) -> MarzbanSubscription:
        if not self.base_url:
            raise MarzbanError("MARZBAN_BASE_URL is not configured")

        access_token = self.token or await self._login()
        proxies, inbounds = await self._resolve_protocol_config(access_token)
        username = self._username(requested_username or f"sub_{buyer.telegram_id}")
        expire = int((datetime.now(UTC) + timedelta(days=offer.duration_days)).timestamp())
        data_limit = offer.traffic_gb * 1024 * 1024 * 1024

        payload = {
            "username": username,
            "proxies": proxies,
            "expire": expire,
            "data_limit": data_limit,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": f"seller-master; buyer_tg={buyer.telegram_id}; traffic_gb={offer.traffic_gb}; duration_days={offer.duration_days}",
        }
        if inbounds:
            payload["inbounds"] = inbounds

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await self._retry_request(
                    lambda: client.post(
                        f"{self.base_url}/api/user",
                        json=payload,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                )
        except httpx.RequestError as exc:
            raise MarzbanError(f"Cannot connect to Marzban panel while creating user: {exc}") from exc

        if response.status_code >= 400:
            raise MarzbanError(f"Marzban user creation failed: {response.status_code} {response.text[:500]}")

        body = response.json()
        subscription_url = self._extract_subscription_url(body) or body.get("subscription_url_prefix") or f"{self.base_url}/sub/{username}"
        return MarzbanSubscription(
            username=body.get("username", username),
            subscription_url=subscription_url,
            expires_at=datetime.fromtimestamp(body.get("expire", expire), UTC).isoformat(),
        )

    async def create_trial_subscription(
        self,
        username: str,
        *,
        data_limit_mb: int,
        duration_days: int,
    ) -> MarzbanSubscription:
        if not self.base_url:
            raise MarzbanError("MARZBAN_BASE_URL is not configured")
        if data_limit_mb < 1:
            raise MarzbanError("Trial data limit must be at least 1 MB")

        access_token = self.token or await self._login()
        proxies, inbounds = await self._resolve_protocol_config(access_token)
        marzban_username = self._username(username)
        expire = int((datetime.now(UTC) + timedelta(days=duration_days)).timestamp())
        data_limit = data_limit_mb * 1024 * 1024

        payload = {
            "username": marzban_username,
            "proxies": proxies,
            "expire": expire,
            "data_limit": data_limit,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": f"trial; traffic_mb={data_limit_mb}; duration_days={duration_days}",
        }
        if inbounds:
            payload["inbounds"] = inbounds

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await self._retry_request(
                    lambda: client.post(
                        f"{self.base_url}/api/user",
                        json=payload,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                )
        except httpx.RequestError as exc:
            raise MarzbanError(f"Cannot connect to Marzban panel while creating trial user: {exc}") from exc

        if response.status_code >= 400:
            raise MarzbanError(f"Marzban trial user creation failed: {response.status_code} {response.text[:500]}")

        body = response.json()
        subscription_url = self._extract_subscription_url(body) or f"{self.base_url}/sub/{marzban_username}"
        return MarzbanSubscription(
            username=body.get("username", marzban_username),
            subscription_url=subscription_url,
            expires_at=datetime.fromtimestamp(body.get("expire", expire), UTC).isoformat(),
        )

    async def revoke_subscription(self, username: str) -> str | None:
        access_token = self.token or await self._login()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await self._retry_request(
                    lambda: client.post(
                        f"{self.base_url}/api/user/{username}/revoke_sub",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                )
        except httpx.RequestError as exc:
            raise MarzbanError(f"Cannot connect to Marzban panel while revoking subscription: {exc}") from exc
        if response.status_code >= 400:
            raise MarzbanError(f"Marzban revoke failed: {response.status_code} {response.text[:500]}")
        body = response.json() if response.content else {}
        return self._extract_subscription_url(body)

    async def extend_subscription(self, username: str, add_gb: int, add_days: int, current_expires_at: str, current_traffic_gb: int) -> MarzbanSubscription:
        access_token = self.token or await self._login()
        base_expire = self._parse_expire(current_expires_at)
        expire = int((base_expire + timedelta(days=add_days)).timestamp())
        payload = {
            "expire": expire,
            "data_limit": (current_traffic_gb + add_gb) * 1024 * 1024 * 1024,
            "status": "active",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await self._retry_request(
                    lambda: client.put(
                        f"{self.base_url}/api/user/{username}",
                        json=payload,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                )
        except httpx.RequestError as exc:
            raise MarzbanError(f"Cannot connect to Marzban panel while extending user {username}: {exc}") from exc
        if response.status_code >= 400:
            raise MarzbanError(f"Marzban extension failed: {response.status_code} {response.text[:500]}")
        body = response.json() if response.content else {}
        return MarzbanSubscription(
            username=body.get("username", username),
            subscription_url=self._extract_subscription_url(body) or f"{self.base_url}/sub/{username}",
            expires_at=datetime.fromtimestamp(body.get("expire", expire), UTC).isoformat(),
        )

    async def fetch_subscription_text(self, subscription_url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(subscription_url)
            response.raise_for_status()
            return response.text or subscription_url
        except (httpx.RequestError, httpx.HTTPStatusError):
            return subscription_url

    def _extract_subscription_url(self, body: dict[str, Any]) -> str | None:
        for key in ("subscription_url", "sub_url", "subscription"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
        links = body.get("links")
        if isinstance(links, list) and links:
            first = links[0]
            return first if isinstance(first, str) else None
        return None

    def _parse_expire(self, value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed = datetime.now(UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        return parsed if parsed > now else now

    async def _resolve_protocol_config(self, access_token: str) -> tuple[dict[str, Any], dict[str, list[str]] | None]:
        default_proxies = self._load_default_proxies()
        if not isinstance(default_proxies, dict) or not default_proxies:
            raise MarzbanError("MARZBAN_DEFAULT_PROXIES_JSON must be a non-empty JSON object")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await self._retry_request(
                    lambda: client.get(
                        f"{self.base_url}/api/inbounds",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                )
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError):
            return default_proxies, None

        inbounds = self._extract_inbounds_by_protocol(response.json())
        if not inbounds:
            return default_proxies, None
        proxies = {protocol: default_proxies.get(protocol, {}) for protocol in inbounds}
        return proxies, inbounds

    def _load_default_proxies(self) -> dict[str, Any]:
        raw = (self.default_proxies_json or "").strip()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            try:
                value, _index = json.JSONDecoder().raw_decode(raw)
            except json.JSONDecodeError:
                raise MarzbanError(f"MARZBAN_DEFAULT_PROXIES_JSON is invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise MarzbanError("MARZBAN_DEFAULT_PROXIES_JSON must be a non-empty JSON object")
        return value

    def _extract_inbounds_by_protocol(self, response: dict[str, Any]) -> dict[str, list[str]]:
        source = response.get("inbounds") if isinstance(response.get("inbounds"), dict) else response
        if not isinstance(source, dict):
            return {}

        parsed: dict[str, list[str]] = {}
        for protocol, raw_inbounds in source.items():
            if protocol in {"detail", "status", "message"}:
                continue
            names = self._extract_inbound_names(raw_inbounds)
            if names:
                parsed[str(protocol)] = names
        return parsed

    def _extract_inbound_names(self, raw_inbounds: Any) -> list[str]:
        if isinstance(raw_inbounds, dict):
            raw_inbounds = raw_inbounds.get("inbounds") or raw_inbounds.get("items") or raw_inbounds.get("tags") or []
        if not isinstance(raw_inbounds, list):
            return []

        names: list[str] = []
        for item in raw_inbounds:
            if isinstance(item, str) and item:
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("tag") or item.get("name") or item.get("remark")
                if isinstance(name, str) and name:
                    names.append(name)
        return names

    def _username(self, requested_username: str) -> str:
        suffix = "".join(secrets.choice(string.ascii_lowercase) for _ in range(3))
        base = re.sub(r"[^a-z0-9_]", "", requested_username.lower()).strip("_")
        if not base:
            base = "sub"
        max_base_length = 32 - 4
        return f"{base[:max_base_length]}_{suffix}"

    async def _login(self) -> str:
        if not self.username or not self.password:
            raise MarzbanError("MARZBAN_USERNAME/MARZBAN_PASSWORD or MARZBAN_TOKEN must be configured")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await self._retry_request(
                    lambda: client.post(f"{self.base_url}/api/admin/token", data={"username": self.username, "password": self.password})
                )
                if response.status_code in (400, 422):
                    response = await self._retry_request(
                        lambda: client.post(
                            f"{self.base_url}/api/admin/token",
                            files={"username": (None, self.username), "password": (None, self.password)},
                        )
                    )
        except httpx.RequestError as exc:
            raise MarzbanError(f"Cannot connect to Marzban panel while logging in: {exc}") from exc
        if response.status_code >= 400:
            raise MarzbanError(f"Marzban login failed: {response.status_code} {response.text[:500]}")
        token = response.json().get("access_token") or response.json().get("token")
        if not token:
            raise MarzbanError("Marzban login response did not include access_token")
        return token
