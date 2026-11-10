from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.security import TokenType, decode_token
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.services.cache import BookCache
from app.services.cart import CartService
from app.services.orders import OrderService

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]


def get_book_cache(redis: RedisClient) -> BookCache:
    return BookCache(redis)


BookCacheDep = Annotated[BookCache, Depends(get_book_cache)]

bearer_scheme = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(db: DbSession, credentials: BearerCredentials) -> User:
    if credentials is None:
        raise unauthorized("Not authenticated")

    try:
        user_id = decode_token(credentials.credentials, TokenType.access)
    except jwt.InvalidTokenError:
        raise unauthorized("Invalid or expired token") from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(user: CurrentUser) -> User:
    if user.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )
    return user


AdminUser = Annotated[User, Depends(get_current_admin)]


def get_cart_service(db: DbSession, user: CurrentUser) -> CartService:
    return CartService(db, user.id)


Cart = Annotated[CartService, Depends(get_cart_service)]


def get_order_service(db: DbSession, user: CurrentUser) -> OrderService:
    return OrderService(db, user)


OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
