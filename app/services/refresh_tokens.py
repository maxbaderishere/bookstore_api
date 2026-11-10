"""Выдача, ротация и отзыв refresh-токенов, хранящихся в таблице refresh_tokens."""

import uuid
from datetime import UTC, datetime

import jwt
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    refresh_token_lifetime,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair


class RefreshTokenError(Exception):
    """Refresh-токен невалиден, просрочен, отозван или принадлежит неактивному юзеру."""


def _now() -> datetime:
    return datetime.now(UTC)


async def _create_record(db: AsyncSession, user_id: int) -> RefreshToken:
    record = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        expires_at=_now() + refresh_token_lifetime(),
    )
    db.add(record)
    await db.flush()
    return record


def _pair(user_id: int, record: RefreshToken) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id, record.id),
    )


async def issue_tokens(db: AsyncSession, user: User) -> TokenPair:
    record = await _create_record(db, user.id)
    await db.commit()
    return _pair(user.id, record)


async def revoke_all(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await db.commit()


async def _load(db: AsyncSession, token: str) -> RefreshToken:
    try:
        user_id, jti = decode_refresh_token(token)
    except jwt.InvalidTokenError as exc:
        raise RefreshTokenError from exc

    # FOR UPDATE: два одновременных refresh одним токеном не пройдут оба
    record = await db.get(RefreshToken, jti, with_for_update=True)
    if record is None or record.user_id != user_id:
        raise RefreshTokenError
    return record


async def rotate(db: AsyncSession, token: str) -> TokenPair:
    """Обменивает refresh-токен на новую пару; старый отзывается."""
    record = await _load(db, token)

    if record.is_revoked:
        # Повторное использование уже отозванного токена — вероятная кража:
        # отзываем все активные токены пользователя.
        await revoke_all(db, record.user_id)
        raise RefreshTokenError
    if record.expires_at <= _now():
        raise RefreshTokenError

    user = await db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise RefreshTokenError

    new_record = await _create_record(db, user.id)
    record.revoked_at = _now()
    record.replaced_by = new_record.id
    await db.commit()

    return _pair(user.id, new_record)


async def revoke(db: AsyncSession, token: str) -> None:
    """Отзывает один refresh-токен (logout). Повторный отзыв — не ошибка."""
    record = await _load(db, token)
    if not record.is_revoked:
        record.revoked_at = _now()
        await db.commit()
