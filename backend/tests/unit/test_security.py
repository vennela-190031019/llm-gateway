from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_does_not_return_plaintext() -> None:
    hashed = hash_password("hunter22")
    assert hashed != "hunter22"


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("hunter22")
    assert verify_password("hunter22", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("hunter22")
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_salts_each_call_differently() -> None:
    assert hash_password("hunter22") != hash_password("hunter22")


def test_create_and_decode_access_token_round_trips_subject() -> None:
    token = create_access_token(subject="user-123")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"


def test_decode_access_token_rejects_expired_token() -> None:
    token = create_access_token(subject="user-123", expires_delta=timedelta(minutes=-1))
    with pytest.raises(ValueError):
        decode_access_token(token)


def test_decode_access_token_rejects_garbage_token() -> None:
    with pytest.raises(ValueError):
        decode_access_token("not-a-real-token")
