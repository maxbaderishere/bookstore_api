"""Юнит-тесты app/core/security.py (без HTTP и БД)."""

import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.config import cfg
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    create_token,
    decode_refresh_token,
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


def test_access_token_roundtrip():
    assert decode_token(create_access_token(42), TokenType.access) == 42


def test_refresh_token_roundtrip():
    jti = uuid.uuid4()

    assert decode_refresh_token(create_refresh_token(42, jti)) == (42, jti)


def test_decode_wrong_token_type():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(create_refresh_token(1, uuid.uuid4()), TokenType.access)
    with pytest.raises(jwt.InvalidTokenError):
        decode_refresh_token(create_access_token(1))


def test_refresh_token_requires_jti():
    token = create_token(1, TokenType.refresh, timedelta(minutes=1))

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_refresh_token(token)


def test_refresh_token_invalid_jti():
    token = jwt.encode(
        {"sub": "1", "type": "refresh", "exp": 9_999_999_999, "jti": "not-a-uuid"},
        cfg.SECRET,
        algorithm=cfg.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_refresh_token(token)


def test_decode_expired_token():
    token = create_token(1, TokenType.access, timedelta(seconds=-1))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, TokenType.access)


def test_decode_garbage():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("not.a.token", TokenType.access)
