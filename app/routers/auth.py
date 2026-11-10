from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import RefreshTokenError
from app.core.security import generate_salt, hash_password, verify_password
from app.dependencies import CurrentUser, DbSession, unauthorized
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserOut
from app.services import refresh_tokens

router = APIRouter(prefix="/auth", tags=["auth"])

# Хэш-заглушка: при неизвестном email всё равно считаем pbkdf2,
# чтобы по времени ответа нельзя было узнать, зарегистрирован ли email.
_DUMMY_SALT = generate_salt()
_DUMMY_HASH = hash_password("dummy-password", _DUMMY_SALT)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(db: DbSession, data: UserCreate):
    salt = generate_salt()
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        salt=salt,
        hashed_password=hash_password(data.password, salt),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        ) from None

    await db.refresh(user)
    return user


async def authenticate(db: DbSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        verify_password(password, _DUMMY_SALT, _DUMMY_HASH)
        raise unauthorized("Incorrect email or password")
    if not verify_password(password, user.salt, user.hashed_password):
        raise unauthorized("Incorrect email or password")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive"
        )
    return user


@router.post("/login", response_model=TokenPair)
async def login(db: DbSession, data: LoginRequest):
    """Вход по JSON. В ответе access_token — для заголовка Authorization,
    refresh_token — для /auth/refresh и /auth/logout."""
    user = await authenticate(db, data.email, data.password)
    return await refresh_tokens.issue_tokens(db, user)


@router.post("/token", response_model=TokenPair)
async def token(db: DbSession, form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Вход по форме OAuth2 — его использует кнопка Authorize в Swagger.
    В поле username передаётся email."""
    user = await authenticate(db, form.username, form.password)
    return await refresh_tokens.issue_tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(db: DbSession, data: RefreshRequest):
    """Ротация: старый refresh-токен отзывается, выдаётся новая пара."""
    try:
        return await refresh_tokens.rotate(db, data.refresh_token)
    except RefreshTokenError:
        raise unauthorized("Invalid or expired refresh token") from None


@router.post("/logout", status_code=204)
async def logout(db: DbSession, data: RefreshRequest):
    """Отзывает переданный refresh-токен."""
    try:
        await refresh_tokens.revoke(db, data.refresh_token)
    except RefreshTokenError:
        raise unauthorized("Invalid refresh token") from None


@router.post("/logout-all", status_code=204)
async def logout_all(db: DbSession, user: CurrentUser):
    """Отзывает все refresh-токены текущего пользователя (выход со всех устройств)."""
    await refresh_tokens.revoke_all(db, user.id)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user
