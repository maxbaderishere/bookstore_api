from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import Role
from app.schemas.out_schema import out_schema


@out_schema
class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=150)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    role: Role | None = None
