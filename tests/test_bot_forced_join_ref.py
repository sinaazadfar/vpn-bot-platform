import pytest

from bot.forced_join import chat_ref_to_get_chat_target


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-1001234567890", "-1001234567890"),
        ("@mychannel", "@mychannel"),
        ("mychannel", "@mychannel"),
        ("https://t.me/mychannel", "@mychannel"),
        ("http://www.t.me/mychannel/join", "@mychannel"),
        ("https://t.me/+AbCdEfGhIj", "https://t.me/+AbCdEfGhIj"),
    ],
)
def test_chat_ref_to_get_chat_target(raw: str, expected: str) -> None:
    assert chat_ref_to_get_chat_target(raw) == expected


def test_chat_ref_to_get_chat_target_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty_ref"):
        chat_ref_to_get_chat_target("   ")
