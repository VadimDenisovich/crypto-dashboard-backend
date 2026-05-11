from __future__ import annotations

import uuid

import pytest

from src.infrastructure import security


def test_password_hash_roundtrip() -> None:
    h = security.hash_password("S3cret!")
    assert h != "S3cret!"
    assert security.verify_password("S3cret!", h)
    assert not security.verify_password("wrong", h)


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = security.encode_access_token(
        user_id=user_id, role="trader", secret="k", algorithm="HS256", ttl_minutes=5
    )
    payload = security.decode_token(token, "k", "HS256")
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "trader"
    assert payload["type"] == "access"


def test_decode_invalid_token() -> None:
    with pytest.raises(ValueError):
        security.decode_token("not-a-token", "k", "HS256")
