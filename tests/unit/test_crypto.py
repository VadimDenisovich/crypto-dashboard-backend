from __future__ import annotations

from cryptography.fernet import Fernet

from src.infrastructure.crypto import Cipher


def test_roundtrip() -> None:
    key = Fernet.generate_key().decode()
    cipher = Cipher(key)
    ct = cipher.encrypt("hello-world")
    assert ct != "hello-world"
    assert cipher.decrypt(ct) == "hello-world"


def test_ciphertext_differs_for_same_input() -> None:
    key = Fernet.generate_key().decode()
    cipher = Cipher(key)
    assert cipher.encrypt("same") != cipher.encrypt("same")
