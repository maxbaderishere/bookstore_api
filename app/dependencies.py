from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.security import TokenType, decode_token
from app.db.session import get_db
from app.models.user import User

DbSession = Annotated[AsyncSession, Depends(get_db)]

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
