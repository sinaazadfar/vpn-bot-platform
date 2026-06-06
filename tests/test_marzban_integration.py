from __future__ import annotations

import datetime as dt

from vpn_bot_platform.integrations.marzban import (
    MarzbanCredentials,
    MarzbanUserCreate,
    MarzbanUserUpdate,
    UsersQuery,
    gb_to_bytes,
    seconds_from_now,
)


def test_credentials_normalize_base_url() -> None:
    credentials = MarzbanCredentials(
        base_url="https://panel.example.com/",
        auth_method="token",
        token="secret",
    )

    assert credentials.normalized_base_url() == "https://panel.example.com"


def test_user_create_payload_omits_none_values() -> None:
    user = MarzbanUserCreate(
        username="buyer_100",
        proxies={"vless": {}},
        data_limit=gb_to_bytes(30),
        expire=seconds_from_now(30),
        note=None,
    )

    payload = user.to_payload()

    assert payload["username"] == "buyer_100"
    assert payload["data_limit"] == 30 * 1024 * 1024 * 1024
    assert payload["data_limit_reset_strategy"] == "no_reset"
    assert "note" not in payload


def test_user_update_payload_allows_partial_updates() -> None:
    update = MarzbanUserUpdate(status="disabled")

    assert update.to_payload() == {"status": "disabled"}


def test_users_query_params() -> None:
    query = UsersQuery(limit=20, admin=["reseller_a"], status="active")

    assert query.to_params() == {
        "limit": 20,
        "admin": ["reseller_a"],
        "status": "active",
    }


def test_seconds_from_now_returns_future_timestamp() -> None:
    now = int(dt.datetime.now(dt.UTC).timestamp())

    assert seconds_from_now(1) > now

