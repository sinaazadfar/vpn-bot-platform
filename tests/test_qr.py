from __future__ import annotations

from vpn_bot_platform.common.qr import make_qr_png_bytes


def test_make_qr_png_bytes_returns_png() -> None:
    data = make_qr_png_bytes("https://panel.example.com/sub/user")

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(data) > 100

