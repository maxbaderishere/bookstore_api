"""Юнит-тесты app/core/security.py (без HTTP и БД)."""

from datetime import timedelta

import jwt
import pytest

from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    create_token,
    decode_token,
    generate_salt,
    hash_password,
    verify_password,
)


def test_generate_salt_is_random_hex():
    first, second = generate_salt(), generate_salt()

    assert first != second
    assert len(bytes.fromhex(first)) == 16


def test_hash_and_verify_password():
    salt = generate_salt()
    hashed = hash_password("secret-password", salt)

    assert hashed != "secret-password"
    assert verify_password("secret-password", salt, hashed)
    assert not verify_password("wrong-password", salt, hashed)


def test_same_password_different_salt_gives_different_hash():
    assert hash_password("password", generate_salt()) != hash_password(
        "password", generate_salt()
    )


def test_verify_password_wrong_salt():
    hashed = hash_password("password", generate_salt())

    assert not verify_password("password", generate_salt(), hashed)


@pytest.mark.parametrize(
    ("factory", "token_type"),
    [
        (create_access_token, TokenType.access),
        (create_refresh_token, TokenType.refresh),
    ],
)
def test_token_roundtrip(factory, token_type):
    assert decode_token(factory(42), token_type) == 42


def test_decode_wrong_token_type():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(create_refresh_token(1), TokenType.access)


def test_decode_expired_token():
    token = create_token(1, TokenType.access, timedelta(seconds=-1))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, TokenType.access)


def test_decode_garbage():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("not.a.token", TokenType.access)
