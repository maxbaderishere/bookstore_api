import hashlib
import hmac
import secrets
import uuid
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


def create_token(
    user_id: int,
    token_type: TokenType,
    expires_in: timedelta,
    *,
    jti: uuid.UUID | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_in,
    }
    if jti is not None:
        payload["jti"] = str(jti)
    return jwt.encode(payload, _secret(), algorithm=cfg.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return create_token(
        user_id,
        TokenType.access,
        timedelta(minutes=cfg.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def refresh_token_lifetime() -> timedelta:
    return timedelta(days=cfg.REFRESH_TOKEN_EXPIRE_DAYS)


def create_refresh_token(user_id: int, jti: uuid.UUID) -> str:
    """jti должен совпадать с id записи RefreshToken в БД."""
    return create_token(user_id, TokenType.refresh, refresh_token_lifetime(), jti=jti)


def _decode(token: str, expected_type: TokenType, required: list[str]) -> dict:
    payload = jwt.decode(
        token,
        _secret(),
        algorithms=[cfg.JWT_ALGORITHM],
        options={"require": ["sub", "type", "exp", *required]},
    )
    if payload["type"] != expected_type.value:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


def _user_id(payload: dict) -> int:
    try:
        return int(payload["sub"])
    except ValueError as exc:
        raise jwt.InvalidTokenError("Invalid subject") from exc


def decode_token(token: str, expected_type: TokenType) -> int:
    """Возвращает id пользователя; бросает jwt.InvalidTokenError при любой проблеме."""
    return _user_id(_decode(token, expected_type, []))


def decode_refresh_token(token: str) -> tuple[int, uuid.UUID]:
    """Возвращает (user_id, jti); бросает jwt.InvalidTokenError при любой проблеме."""
    payload = _decode(token, TokenType.refresh, ["jti"])
    try:
        jti = uuid.UUID(payload["jti"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError("Invalid jti") from exc
    return _user_id(payload), jti
