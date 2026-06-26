from __future__ import annotations

import httpx
import pytest

from bot.db import PurchaseOffer, User
from bot.marzban import MarzbanClient


@pytest.mark.asyncio
async def test_marzban_create_user_sends_proxies_and_inbounds(monkeypatch):
    requests: list[httpx.Request] = []
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "token"})
        if request.url.path == "/api/inbounds":
            return httpx.Response(
                200,
                json={
                    "vless": [{"tag": "VLESS TCP REALITY"}],
                    "vmess": [{"tag": "VMess WS TLS"}],
                },
            )
        if request.url.path == "/api/user":
            payload = __import__("json").loads(request.content)
            assert payload["proxies"] == {"vless": {}, "vmess": {}}
            assert payload["inbounds"] == {
                "vless": ["VLESS TCP REALITY"],
                "vmess": ["VMess WS TLS"],
            }
            assert payload["data_limit"] == 10 * 1024 * 1024 * 1024
            assert payload["status"] == "active"
            return httpx.Response(
                200,
                json={
                    "username": payload["username"],
                    "subscription_url": "https://panel.example/sub/user",
                    "expire": payload["expire"],
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)))
    client = MarzbanClient("https://panel.example", "admin", "pass", "", '{"vless":{},"vmess":{},"trojan":{}}')

    result = await client.create_subscription(
        PurchaseOffer(traffic_gb=10, duration_days=30, source="manual", discount_percent=0, base_price=0, duration_extra=0, final_price=0),
        User(id=1, telegram_id=123456, role="buyer", wallet_balance=0, referral_code="abc", referred_by=None),
    )

    assert result.subscription_url == "https://panel.example/sub/user"
    assert [request.url.path for request in requests] == ["/api/admin/token", "/api/inbounds", "/api/user"]


def test_marzban_username_uses_requested_name_and_three_letter_suffix():
    client = MarzbanClient("https://panel.example", token="token")

    username = client._username("My_User")
    suffix = username.rsplit("_", 1)[1]

    assert username.startswith("my_user_")
    assert len(suffix) == 3
    assert suffix.isalpha()
    assert username == username.lower()
    assert len(username) <= 32


def test_marzban_username_cleans_requested_name():
    client = MarzbanClient("https://panel.example", token="token")

    username = client._username("Ali-Reza 123")

    assert username.startswith("alireza123_")


def test_marzban_default_proxies_accepts_valid_object_with_trailing_data():
    client = MarzbanClient("https://panel.example", token="token", default_proxies_json='{"vless": {}} extra')

    assert client._load_default_proxies() == {"vless": {}}


@pytest.mark.asyncio
async def test_marzban_revoke_returns_new_subscription_url(monkeypatch):
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/user/user_abc/revoke_sub"
        return httpx.Response(200, json={"subscription_url": "https://panel.example/sub/new"})

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)))
    client = MarzbanClient("https://panel.example", token="token")

    assert await client.revoke_subscription("user_abc") == "https://panel.example/sub/new"


@pytest.mark.asyncio
async def test_marzban_extend_updates_expire_and_data_limit(monkeypatch):
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/api/user/user_abc"
        payload = __import__("json").loads(request.content)
        assert payload["data_limit"] == 15 * 1024 * 1024 * 1024
        assert payload["status"] == "active"
        return httpx.Response(
            200,
            json={
                "username": "user_abc",
                "subscription_url": "https://panel.example/sub/user_abc",
                "expire": payload["expire"],
            },
        )

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)))
    client = MarzbanClient("https://panel.example", token="token")

    result = await client.extend_subscription("user_abc", 5, 30, "2026-07-20T00:00:00+00:00", 10)

    assert result.username == "user_abc"
    assert result.subscription_url == "https://panel.example/sub/user_abc"


@pytest.mark.asyncio
async def test_fetch_subscription_text_falls_back_to_url(monkeypatch):
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)))
    client = MarzbanClient("https://panel.example", token="token")

    assert await client.fetch_subscription_text("https://panel.example/sub/user") == "https://panel.example/sub/user"


@pytest.mark.asyncio
async def test_marzban_falls_back_to_default_proxies_when_inbounds_fails(monkeypatch):
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/inbounds":
            return httpx.Response(500, text="no inbounds")
        if request.url.path == "/api/user":
            payload = __import__("json").loads(request.content)
            assert payload["proxies"] == {"vless": {}}
            assert "inbounds" not in payload
            return httpx.Response(200, json={"username": payload["username"], "subscription_url": "https://panel.example/sub/user"})
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)))
    client = MarzbanClient("https://panel.example", token="token", default_proxies_json='{"vless":{}}')

    result = await client.create_subscription(
        PurchaseOffer(traffic_gb=5, duration_days=90, source="manual", discount_percent=0, base_price=0, duration_extra=0, final_price=0),
        User(id=1, telegram_id=123456, role="buyer", wallet_balance=0, referral_code="abc", referred_by=None),
    )

    assert result.subscription_url == "https://panel.example/sub/user"


@pytest.mark.asyncio
async def test_marzban_create_trial_subscription_uses_mb_limit(monkeypatch):
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/user":
            payload = __import__("json").loads(request.content)
            assert payload["data_limit"] == 512 * 1024 * 1024
            assert payload["status"] == "active"
            return httpx.Response(
                200,
                json={
                    "username": payload["username"],
                    "subscription_url": "https://panel.example/sub/trial",
                    "expire": payload["expire"],
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)))
    client = MarzbanClient("https://panel.example", token="token", default_proxies_json='{"vless":{}}')

    result = await client.create_trial_subscription("trial_123", data_limit_mb=512, duration_days=1)

    assert result.subscription_url == "https://panel.example/sub/trial"
