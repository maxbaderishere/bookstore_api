import jwt
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_salt,
    hash_password,
    verify_password,
)
from app.dependencies import CurrentUser, DbSession, unauthorized
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Хэш-заглушка: при неизвестном email всё равно считаем pbkdf2,
# чтобы по времени ответа нельзя было узнать, зарегистрирован ли email.
_DUMMY_SALT = generate_salt()
_DUMMY_HASH = hash_password("dummy-password", _DUMMY_SALT)


def issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


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


@router.post("/login", response_model=TokenPair)
async def login(db: DbSession, data: LoginRequest):
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        verify_password(data.password, _DUMMY_SALT, _DUMMY_HASH)
        raise unauthorized("Incorrect email or password")
    if not verify_password(data.password, user.salt, user.hashed_password):
        raise unauthorized("Incorrect email or password")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive"
        )

    return issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(db: DbSession, data: RefreshRequest):
    try:
        user_id = decode_token(data.refresh_token, TokenType.refresh)
    except jwt.InvalidTokenError:
        raise unauthorized("Invalid or expired refresh token") from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized("User not found or inactive")

    return issue_tokens(user)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user
