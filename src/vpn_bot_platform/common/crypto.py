from __future__ import annotations

import hashlib

from cryptography.fernet import Fernet, InvalidToken


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SecretBox:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("utf-8"))

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        if value == "":
            return ""
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        if value == "":
            return ""
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return None

