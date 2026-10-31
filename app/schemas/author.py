from pydantic import BaseModel, Field

from app.schemas.common import Year
from app.schemas.out_schema import out_schema


class AuthorCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    birth_year: Year | None = None
    bio: str | None = None


class AuthorUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    bio: str | None = None
    birth_year: Year | None = None


@out_schema
class AuthorShort(BaseModel):
    id: int
    full_name: str


class AuthorOut(AuthorShort):
    bio: str | None = None
    birth_year: int | None = None