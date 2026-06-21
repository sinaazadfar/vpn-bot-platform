from bot.qr import make_qr_png


def test_make_qr_png_returns_png_bytes():
    data = make_qr_png("https://panel.example/sub/user")

    assert data.startswith(b"\x89PNG")
