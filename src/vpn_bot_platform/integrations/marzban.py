from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx


AuthMethod = Literal["token", "password"]
UserStatus = Literal["active", "disabled", "limited", "expired"]
DataLimitResetStrategy = Literal["no_reset", "day", "week", "month", "year"]


class MarzbanError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarzbanCredentials:
    base_url: str
    auth_method: AuthMethod
    token: str | None = None
    username: str | None = None
    password: str | None = None
    token_path: str = "/api/admin/token"
    timeout_seconds: int = 20

    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


@dataclass(frozen=True)
class MarzbanUserCreate:
    username: str
    proxies: dict[str, Any]
    inbounds: dict[str, list[str]] | None = None
    expire: int | None = None
    data_limit: int | None = None
    data_limit_reset_strategy: DataLimitResetStrategy = "no_reset"
    status: UserStatus = "active"
    note: str | None = None
    on_hold_expire_duration: int | None = None
    on_hold_timeout: str | None = None
    next_plan: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "username": self.username,
            "proxies": self.proxies,
            "data_limit_reset_strategy": self.data_limit_reset_strategy,
            "status": self.status,
        }
        optional_values = {
            "inbounds": self.inbounds,
            "expire": self.expire,
            "data_limit": self.data_limit,
            "note": self.note,
            "on_hold_expire_duration": self.on_hold_expire_duration,
            "on_hold_timeout": self.on_hold_timeout,
            "next_plan": self.next_plan,
        }
        payload.update({key: value for key, value in optional_values.items() if value is not None})
        return payload


@dataclass(frozen=True)
class MarzbanUserUpdate:
    proxies: dict[str, Any] | None = None
    inbounds: dict[str, list[str]] | None = None
    expire: int | None = None
    data_limit: int | None = None
    data_limit_reset_strategy: DataLimitResetStrategy | None = None
    status: UserStatus | None = None
    note: str | None = None
    next_plan: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        values = {
            "proxies": self.proxies,
            "inbounds": self.inbounds,
            "expire": self.expire,
            "data_limit": self.data_limit,
            "data_limit_reset_strategy": self.data_limit_reset_strategy,
            "status": self.status,
            "note": self.note,
            "next_plan": self.next_plan,
        }
        return {key: value for key, value in values.items() if value is not None}


@dataclass(frozen=True)
class UsersQuery:
    offset: int | None = None
    limit: int | None = None
    username: list[str] = field(default_factory=list)
    search: str | None = None
    admin: list[str] = field(default_factory=list)
    status: UserStatus | None = None
    sort: str | None = None

    def to_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.offset is not None:
            params["offset"] = self.offset
        if self.limit is not None:
            params["limit"] = self.limit
        if self.username:
            params["username"] = self.username
        if self.search is not None:
            params["search"] = self.search
        if self.admin:
            params["admin"] = self.admin
        if self.status is not None:
            params["status"] = self.status
        if self.sort is not None:
            params["sort"] = self.sort
        return params


class MarzbanClient:
    def __init__(self, credentials: MarzbanCredentials) -> None:
        self.credentials = credentials
        self.base_url = credentials.normalized_base_url()
        self._cached_token: str | None = None

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
        if last_error is not None:
            raise last_error
        raise MarzbanError("Unexpected retry state")

    async def _fetch_password_token(self) -> str | None:
        if not self.credentials.username or not self.credentials.password:
            return None

        token_url = f"{self.base_url}{self.credentials.token_path}"
        async with httpx.AsyncClient(timeout=self.credentials.timeout_seconds) as client:
            try:
                response = await self._retry_request(
                    lambda: client.post(
                        token_url,
                        data={
                            "username": self.credentials.username,
                            "password": self.credentials.password,
                        },
                    )
                )
                response.raise_for_status()
            except (httpx.RequestError, httpx.HTTPStatusError):
                response = await self._retry_request(
                    lambda: client.post(
                        token_url,
                        files={
                            "username": (None, self.credentials.username),
                            "password": (None, self.credentials.password),
                        },
                    )
                )
                response.raise_for_status()

        data = response.json()
        token = data.get("access_token") or data.get("token")
        if not isinstance(token, str) or not token:
            raise MarzbanError("Marzban token response did not include an access token")
        self._cached_token = token
        return token

    async def _bearer_token(self) -> str | None:
        if self.credentials.auth_method == "token":
            return self.credentials.token
        if self._cached_token:
            return self._cached_token
        return await self._fetch_password_token()

    async def _headers(self, *, auth: bool) -> dict[str, str]:
        if not auth:
            return {}
        token = await self._bearer_token()
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        auth: bool = True,
    ) -> Any:
        headers = await self._headers(auth=auth)
        async with httpx.AsyncClient(timeout=self.credentials.timeout_seconds) as client:
            response = await self._retry_request(
                lambda: client.request(
                    method,
                    f"{self.base_url}{path}",
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    headers=headers,
                )
            )
        response.raise_for_status()
        return response.json() if response.content else {"status": "ok"}

    async def admin_token(self, username: str, password: str) -> dict[str, Any]:
        try:
            return await self.request(
                "POST",
                self.credentials.token_path,
                data={"username": username, "password": password},
                auth=False,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (400, 422):
                raise
        return await self.request(
            "POST",
            self.credentials.token_path,
            files={"username": (None, username), "password": (None, password)},
            auth=False,
        )

    async def get_current_admin(self) -> dict[str, Any]:
        return await self.request("GET", "/api/admin")

    async def create_user(self, user: MarzbanUserCreate | dict[str, Any]) -> dict[str, Any]:
        payload = user.to_payload() if isinstance(user, MarzbanUserCreate) else user
        return await self.request("POST", "/api/user", json=payload)

    async def update_user(
        self,
        username: str,
        update: MarzbanUserUpdate | dict[str, Any],
    ) -> dict[str, Any]:
        payload = update.to_payload() if isinstance(update, MarzbanUserUpdate) else update
        return await self.request("PUT", f"/api/user/{username}", json=payload)

    async def get_user(self, username: str) -> dict[str, Any]:
        return await self.request("GET", f"/api/user/{username}")

    async def delete_user(self, username: str) -> dict[str, Any]:
        return await self.request("DELETE", f"/api/user/{username}")

    async def list_users(self, query: UsersQuery | None = None) -> dict[str, Any]:
        params = query.to_params() if query else None
        return await self.request("GET", "/api/users", params=params or None)

    async def reset_user_data_usage(self, username: str) -> dict[str, Any]:
        return await self.request("POST", f"/api/user/{username}/reset")

    async def revoke_user_subscription(self, username: str) -> dict[str, Any]:
        return await self.request("POST", f"/api/user/{username}/revoke_sub")

    async def active_next_plan(self, username: str) -> dict[str, Any]:
        return await self.request("POST", f"/api/user/{username}/active-next")

    async def set_owner(self, username: str, admin_username: str) -> dict[str, Any]:
        return await self.request(
            "PUT",
            f"/api/user/{username}/set-owner",
            params={"admin_username": admin_username},
        )

    async def get_user_usage(
        self,
        username: str,
        *,
        start: dt.datetime | str | None = None,
        end: dt.datetime | str | None = None,
    ) -> dict[str, Any]:
        return await self.request(
            "GET",
            f"/api/user/{username}/usage",
            params=_date_range_params(start=start, end=end),
        )

    async def get_users_usage(
        self,
        *,
        start: dt.datetime | str | None = None,
        end: dt.datetime | str | None = None,
        admin: str | None = None,
    ) -> dict[str, Any]:
        params = _date_range_params(start=start, end=end)
        if admin is not None:
            params["admin"] = admin
        return await self.request("GET", "/api/users/usage", params=params or None)

    async def get_inbounds(self) -> dict[str, Any]:
        return await self.request("GET", "/api/inbounds")

    async def get_nodes(self) -> list[dict[str, Any]]:
        return await self.request("GET", "/api/nodes")


def seconds_from_now(days: int) -> int:
    return int((dt.datetime.now(dt.UTC) + dt.timedelta(days=days)).timestamp())


def gb_to_bytes(gigabytes: int) -> int:
    return gigabytes * 1024 * 1024 * 1024


def _date_range_params(
    *,
    start: dt.datetime | str | None,
    end: dt.datetime | str | None,
) -> dict[str, str] | None:
    params: dict[str, str] = {}
    if start is not None:
        params["start"] = _format_datetime(start)
    if end is not None:
        params["end"] = _format_datetime(end)
    return params or None


def _format_datetime(value: dt.datetime | str) -> str:
    if isinstance(value, str):
        return value
    return value.isoformat()

