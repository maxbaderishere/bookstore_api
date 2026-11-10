import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt

from app.core.config import cfg

PBKDF2_ITERATIONS = 600_000  # рекомендация OWASP для pbkdf2-sha256


class TokenType(StrEnum):
    access = "access"
    refresh = "refresh"


# ---------- пароли ----------


def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return digest.hex()


def verify_password(password: str, salt: str, hashed_password: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), hashed_password)


# ---------- JWT ----------


def _secret() -> str:
    if not cfg.SECRET:
        raise RuntimeError("SECRET is not configured")
    return cfg.SECRET


def create_token(user_id: int, token_type: TokenType, expires_in: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, _secret(), algorithm=cfg.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return create_token(
        user_id,
        TokenType.access,
        timedelta(minutes=cfg.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    return create_token(
        user_id,
        TokenType.refresh,
        timedelta(days=cfg.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: TokenType) -> int:
    """Возвращает id пользователя; бросает jwt.InvalidTokenError при любой проблеме."""
    payload = jwt.decode(
        token,
        _secret(),
        algorithms=[cfg.JWT_ALGORITHM],
        options={"require": ["sub", "type", "exp"]},
    )
    if payload["type"] != expected_type.value:
        raise jwt.InvalidTokenError("Wrong token type")
    try:
        return int(payload["sub"])
    except ValueError as exc:
        raise jwt.InvalidTokenError("Invalid subject") from exc
